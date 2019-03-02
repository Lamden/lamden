.PHONY: new checkdeps

help:
	@echo ""
	@echo "==============================================="
	@echo "|| Cilantro DevOps environment Makefile help ||"
	@echo "==============================================="
	@echo ""
	@echo "Common use-case examples:"
	@echo "========================="
	@echo " -- make new"
	@echo "     Create a new environment"
	@echo ""
	@echo "Available Targets:"
	@echo "=================="
	@echo " -- make new            	Create a new environment, interactive, runs 'checkdeps' prior"
	@echo " -- make checkdeps		Check to see if all necessary dependencies are installed"
	@echo ""
	@echo "Help:"
	@echo "====="
	@echo "If you are attempting to run a given environment, please cd into that environments directory."
	@echo "You can then run 'make help' there for a list of available commands"
	@echo ""

# Make a new environment interactively with create_configs script
new: checkdeps
	python3 ../tools/create_configs.py

# Check if all necessary dependencies exist before running them
checkdeps:
ifeq (,$(shell which terraform))
	$(error "No terraform in path, please install through your package manager e.g. MacOS 'brew install terraform'")
endif
ifeq (,$(shell pip3 freeze | grep pathspec | cut -d'=' -f 1))
	$(error "Package pathspec not available to python3, please install via your python package manager (e.g. 'pip3 install pathspec')")
endif
