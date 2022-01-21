# Stack builder documentation

The **stack-builder** tool **`sb.py`** allows to automate the deployment and updating of the SIB
software stack.
Essentially, *stack-builder* parses an input text file - `sib_stack_package_list.txt` - and build
the listed software packages in the specified order (as well as all their required dependencies).

### Requirements
* python >= 3.6
* `GitPython` module (can be installed with `pip3 install --user GitPython`).
* For python 3.6 only: `dataclasses` module (can be installed with `pip3 install --user dataclasses`)

<br>
<br>


## Set-up and configuration

### stack-builder setup
To setup *stack-builder* for first use, please:
* Clone the present repository: `git clone https://github.com/sib-swiss/stack-builder.git stack-builder.git`
* Install all dependencies of stack-builder on your local machine - see the **Requirements**
  section above.
* Clone the [`sib-software-stack.git`](https://github.com/sib-swiss/sib-software-stack) and
  [`sib-easyconfigs.git`](https://github.com/sib-swiss/easybuild-easyconfigs) git repos, as
  instructed [in this document](https://github.com/sib-swiss/sib-software-stack#readme).
* Make a copy of the `config_stackbuilder.cfg.template` file and rename it as
  `config_easybuild.cfg`. This file should be stored in either:
    * The same location as your EasyBuild configuration file (e.g. `~/.config/easybuild`).
    * Any custom location, but in this case a `STACKBUILDER_CONFIGFILES` environment variable
      indicating the location of the file must be added to the shell environment.
      ```
      export STACKBUILDER_CONFIGFILES=/path/to/sib-software-stack.git/config_stackbuilder.cfg
      ```

### stack-builder configuration
Configuration of the *stack-builder* is done via the `config_stackbuilder.cfg` file.

The following arguments are available:
* **`sib_easyconfigs_repo`:** path to the `sib-easyconfigs.git` directory.
* **`sib_software_stack_repo`:** path to the `sib-software-stack.git` directory.
* **`sib_node`:** the name assigned to your institution, i.e. one of `ibu` `scicore`, `ubelix`, or
  `vitalit`.
* **`allow_reset_node_branch`:** how to handle resetting of your personal work branch (i.e. the
    branch specified under `sib_node`) to its upstream branch (`origin/<branch name>`).
    Possible values for this arguments are:
     * `interactive`: each time a branch reset has to be performed, the user will be prompted for
       an interactive answer.
     * `yes`: always accept branch rebase operations. Please note that this can potentially result
       in commit losses on your local branch if you are not careful to always push new commits on
       your work branch to the remote.
     * `no`: always reject branch rebase operations.
* **`allow_reset_other_nodes_branch`:** same as `allow_reset_node_branch`, but for the work
  branches of nodes other than your own. In principle each node/institution will work on their own
  branch only, and therefore this argument can be set to `yes` fairly safely.

* **`other_nodes`:** under construction... this option is not implemented yet.
* **`optional_software`:** under construction... this option is not implemented yet.

<br>
<br>


## Commands overview
*stack-builder* has 2 main commands:
* **`build`/`bs`/`build-stack`:** builds or updates a local instance of the SIB software stack.

* **`update`/`ur`/`update-repos`:** updates the local instances of the `sib-easyconfigs.git` and
  `sib-software-stack.git` git repositories from the remote.

  `--from-upstream`/`-u`

### Update repository
The **`update`/`ur`** command updates the local instances of the `sib-easyconfigs.git` and
`sib-software-stack.git` git repositories from their respective remotes.

To additionally fetch updates from the
[official EasyBuild easyconfigs repository](https://github.com/easybuilders/easybuild-easyconfigs),
the **`--from-upstream`/`-u`** option can be passed. When using this option, updates from the
*EasyBuild* repo for the `develop` and `main` branches are fetched, merged into the local
instance of the `sib-easyconfigs` repository, and pushed to the
[sib-easyconfigs remote](https://github.com/sib-swiss/easybuild-easyconfigs).

```
sb.py update
sb.py update -u   # Fetches updates from EasyBuild, updates the local repo, and pushes the updates
                  # to the sib-easyconfigs remote.
```

### Build stack
To build the entire software stack, the following commands can be used:
```
sb.py --summary   # Display a summary of the tasks to perform.
sb.py --dry-run   # Do a test-run: this will check that all easyconfig files are found.
sb.py             # Run the actual build.
```

All available options and their shortcuts can be displayed with `./stack_builder.py --help`
