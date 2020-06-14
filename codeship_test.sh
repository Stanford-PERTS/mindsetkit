#!/bin/bash

# Commands to be run during a codeship build of the Mindset Kit.
# In a codeship project, in the Setup Commands window, enter this:

# chmod +x codeship_test.sh && ./codeship_test.sh

# Run python unit tests
python run_python_unit_tests_in_codeship.py
