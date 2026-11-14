
- Update repo_search_query to include a max stars so we can search for repos in ranges.


## General changes

- repo_record / test_record, shold be in the repo_ref and playwright_test modules respectively to keep the models dir clean.

- Remove the test extraction scripts. Extraction / analysis will be done manually


## ghapi

### gateway

Interfaces between this application and GitHub using a PAT. It handles converting gh objects into domain specific obejcts.

- Fetch a repoRef of a specific repo by URL
- Execute a query and return a list of RepoRefs
- Able to resolve a commit of a git repo

### repo_writer

- Does a shallow + safe clone of a repo into an IO
- Can write a repo to IO, delete a repo from IO. Both operation 

- Takes in an implementation of a repoIOmanager, so repos can be written to different file systems etc. (strategy pattern)
- repoOnDiskManager is the implementation that handles writing a repo into a temprorary working directory. It knows how to create a local `tmp` directory, create repo-specific subfolders, and delete them when aksed. This layer handles the interaction between repo cloning and the actual disk. 

### Repo Reader

- Performs checks to see if a repo uses playwright. Should be comprised of several .has_some_property -> bool functions so calleers can decide what to check for.

## Pipelines

Specific workflows / extraction scripts that compose the different components

### Find Repos with Playwright

### Clone Repo into local file dir