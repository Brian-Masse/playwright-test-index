import ast
from pathlib import Path
from typing import Protocol

import tree_sitter_typescript
from models.language import Language
from models.playwright_test import PlaywrightTestSource
from tree_sitter import Language as TreeSitterLanguage
from tree_sitter import Node, Parser

FILE_ENCODING: str = "utf-8"
TITLE_SEPARATOR: str = " > "

PYTHON_TEST_PREFIX: str = "test"
PYTHON_TEST_CLASS_PREFIX: str = "Test"

TS_TEST_ROOTS: frozenset[str] = frozenset({"test", "it"})
TS_DESCRIBE: str = "describe"
TS_TEST_MODIFIERS: frozenset[str] = frozenset({"only", "skip", "fixme", "fail", "slow"})
TS_STRING_TYPES: frozenset[str] = frozenset({"string", "template_string"})
TS_FUNCTION_TYPES: frozenset[str] = frozenset({"arrow_function", "function_expression"})
TS_JSX_SUFFIXES: frozenset[str] = frozenset({".tsx", ".jsx", ".js", ".mjs", ".cjs"})
TS_CALL_TYPE: str = "call_expression"
TS_MEMBER_TYPE: str = "member_expression"
TS_IDENTIFIER_TYPE: str = "identifier"


# MARK: TestExtractor
class TestExtractor(Protocol):
    """Extracts individual Playwright tests from a source file on disk."""

    # MARK: extract_tests
    def extract_tests(self, file_path: Path) -> list[PlaywrightTestSource]:
        """Returns every test declared in the file, in source order."""

        ...


# MARK: PythonTestExtractor
class PythonTestExtractor:
    """Extracts pytest-playwright tests: `test*` functions at module level or in `Test*` classes."""

    # MARK: extract_tests
    def extract_tests(self, file_path: Path) -> list[PlaywrightTestSource]:
        """Returns every test declared in the file, in source order."""

        source: str = file_path.read_text(encoding=FILE_ENCODING, errors="replace")
        module: ast.Module = ast.parse(source, filename=str(file_path))
        source_lines: list[str] = source.splitlines()

        return self._collect_tests(module.body, [], source_lines)

    def _collect_tests(
        self, statements: list[ast.stmt], title_path: list[str], source_lines: list[str]
    ) -> list[PlaywrightTestSource]:
        tests: list[PlaywrightTestSource] = []

        for statement in statements:
            if isinstance(statement, ast.ClassDef) and statement.name.startswith(
                PYTHON_TEST_CLASS_PREFIX
            ):
                tests.extend(
                    self._collect_tests(
                        statement.body, [*title_path, statement.name], source_lines
                    )
                )
            elif isinstance(
                statement, (ast.FunctionDef, ast.AsyncFunctionDef)
            ) and statement.name.startswith(PYTHON_TEST_PREFIX):
                tests.append(self._to_test_source(statement, title_path, source_lines))

        return tests

    @staticmethod
    def _to_test_source(
        function: ast.FunctionDef | ast.AsyncFunctionDef,
        title_path: list[str],
        source_lines: list[str],
    ) -> PlaywrightTestSource:
        start_line: int = min(
            [
                function.lineno,
                *(decorator.lineno for decorator in function.decorator_list),
            ]
        )
        end_line: int = function.end_lineno or function.lineno

        return PlaywrightTestSource(
            title=TITLE_SEPARATOR.join([*title_path, function.name]),
            start_line=start_line,
            end_line=end_line,
            language=Language.python,
            source="\n".join(source_lines[start_line - 1 : end_line]),
        )


# MARK: TypeScriptTestExtractor
class TypeScriptTestExtractor:
    """Extracts @playwright/test tests: `test(...)` calls, titled by their enclosing `test.describe` groups."""

    def __init__(self) -> None:
        self._typescript_parser: Parser = Parser(
            TreeSitterLanguage(tree_sitter_typescript.language_typescript())
        )
        self._tsx_parser: Parser = Parser(
            TreeSitterLanguage(tree_sitter_typescript.language_tsx())
        )

    # MARK: extract_tests
    def extract_tests(self, file_path: Path) -> list[PlaywrightTestSource]:
        """Returns every test declared in the file, in source order."""

        parser: Parser = (
            self._tsx_parser
            if file_path.suffix in TS_JSX_SUFFIXES
            else self._typescript_parser
        )
        root: Node = parser.parse(file_path.read_bytes()).root_node

        return self._collect_tests(root, [])

    def _collect_tests(
        self, node: Node, title_path: list[str]
    ) -> list[PlaywrightTestSource]:
        if node.type == TS_CALL_TYPE:
            callee_chain: list[str] = self._callee_chain(node)
            arguments: list[Node] = self._arguments(node)

            if self._is_describe(callee_chain):
                return self._collect_describe(arguments, title_path)
            if self._is_test(callee_chain, arguments):
                return [self._to_test_source(node, arguments[0], title_path)]

        tests: list[PlaywrightTestSource] = []
        for child in node.named_children:
            tests.extend(self._collect_tests(child, title_path))

        return tests

    def _collect_describe(
        self, arguments: list[Node], title_path: list[str]
    ) -> list[PlaywrightTestSource]:
        group_path: list[str] = (
            [*title_path, self._string_value(arguments[0])]
            if arguments and arguments[0].type in TS_STRING_TYPES
            else title_path
        )

        tests: list[PlaywrightTestSource] = []
        for argument in arguments:
            if argument.type in TS_FUNCTION_TYPES:
                tests.extend(self._collect_tests(argument, group_path))

        return tests

    @staticmethod
    def _to_test_source(
        call: Node, title_node: Node, title_path: list[str]
    ) -> PlaywrightTestSource:
        title: str = TypeScriptTestExtractor._string_value(title_node)
        source: bytes = call.text or b""

        return PlaywrightTestSource(
            title=TITLE_SEPARATOR.join([*title_path, title]),
            start_line=call.start_point.row + 1,
            end_line=call.end_point.row + 1,
            language=Language.typescript,
            source=source.decode(FILE_ENCODING, errors="replace"),
        )

    @staticmethod
    def _callee_chain(call: Node) -> list[str]:
        """Flattens a callee like `test.describe.serial` into ["test", "describe", "serial"]."""

        chain: list[str] = []
        current: Node | None = call.child_by_field_name("function")

        while current is not None and current.type == TS_MEMBER_TYPE:
            property_node: Node | None = current.child_by_field_name("property")
            chain.insert(0, TypeScriptTestExtractor._text(property_node))
            current = current.child_by_field_name("object")

        if current is None or current.type != TS_IDENTIFIER_TYPE:
            return []

        return [TypeScriptTestExtractor._text(current), *chain]

    @staticmethod
    def _arguments(call: Node) -> list[Node]:
        arguments_node: Node | None = call.child_by_field_name("arguments")

        return list(arguments_node.named_children) if arguments_node else []

    @staticmethod
    def _is_describe(callee_chain: list[str]) -> bool:
        return (
            len(callee_chain) >= 2
            and callee_chain[0] in TS_TEST_ROOTS
            and callee_chain[1] == TS_DESCRIBE
        )

    @staticmethod
    def _is_test(callee_chain: list[str], arguments: list[Node]) -> bool:
        is_test_callee: bool = len(callee_chain) == 1 or (
            len(callee_chain) == 2 and callee_chain[1] in TS_TEST_MODIFIERS
        )
        has_title: bool = bool(arguments) and arguments[0].type in TS_STRING_TYPES
        has_body: bool = any(
            argument.type in TS_FUNCTION_TYPES for argument in arguments
        )

        return (
            bool(callee_chain)
            and callee_chain[0] in TS_TEST_ROOTS
            and is_test_callee
            and has_title
            and has_body
        )

    @staticmethod
    def _string_value(string_node: Node) -> str:
        """Strips the surrounding quotes or backticks, keeping `${...}` placeholders verbatim."""

        return TypeScriptTestExtractor._text(string_node)[1:-1]

    @staticmethod
    def _text(node: Node | None) -> str:
        if node is None or node.text is None:
            return ""

        return node.text.decode(FILE_ENCODING, errors="replace")
