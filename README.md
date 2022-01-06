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
To setup *stack-builder* for first use, please:
* Clone the present repository: `git clone https://github.com/sib-swiss/stack-builder.git stack-builder.git`
* Install all dependencies of *stack-builder* on your local machine - see the **Requirements**
  section above.
* Clone the [`sib-software-stack.git`](https://github.com/sib-swiss/sib-software-stack) and
  [`sib-easyconfigs.git`](https://github.com/sib-swiss/easybuild-easyconfigs) git repos, as
  instructed [in this document](https://github.com/sib-swiss/sib-software-stack#readme).
* Make sure the configuration files `config_easybuild.cfg` and `config_stackbuilder.cfg` are
  present and correctly configured for your local machine (see below).


### `config_stackbuilder.cfg` configuration file

To be completed...

### `config_easybuild.cfg` configuration file

To be completed...


<br>
<br>


## Commands overview
*stack-builder* has 2 main commands:
* **`build-stack`:** build or update a local instance of the SIB software stack. Shortcuts for this
  command are **`build`** and **`bs`**
* **`update-repos`:** update the local instances of the `sib-easyconfigs.git` and
  `sib-software-stack.git` git repositories. Shortcuts for this command are **`update`** and
  **`ur`**

### update-repos
Updates the local instances of the `sib-easyconfigs.git` and `sib-software-stack.git` git repositories.
```
./sb.py update-repos
./sb.py update
./sb.py ur
```


### build-stack
To build the entire software stack, the following commands can be used:
```
stack_builder.py --summary   # Display a summary of the tasks to perform.
stack_builder.py --dry-run   # Do a test-run: this will check that all easyconfig files are found.
stack_builder.py             # Run the actual build.
```

All available options and their shortcuts can be displayed with `./stack_builder.py --help`
