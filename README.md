# Stack builder documentation

The **stack builder** tool `sb.py` is a wrapper around EasyBuild that automates the build of the
SIB software stack.
Essentially, the stack builder parses a text file [`sib_stack_package_list.txt`] and build the
listed software packages in the specified order (as well as all their required dependencies).

Before using the stack builder, make sure that your environment is setup as instructed here:
https://github.com/sib-swiss/sib-software-stack#readme.

### Requirements
* python >= 3.6
* GitPython (can be installed with `pip install GitPython`).


<br>
<br>


## Commands overview
To build the entire software stack, the following commands can be used:
```
stack_builder.py --summary   # Display a summary of the tasks to perform.
stack_builder.py --dry-run   # Do a test-run: this will check that all easyconfig files are found.
stack_builder.py             # Run the actual build.
```

All available options and their shortcuts can be displayed with `./stack_builder.py --help`
