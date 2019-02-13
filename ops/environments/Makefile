.PHONY: new

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
	@echo " -- make new            	Create a new environment, interactive"
	@echo ""
	@echo "Help:"
	@echo "====="
	@echo "If you are attempting to run a given environment, please cd into that environments directory."
	@echo "You can then run 'make help' there for a list of available commands"
	@echo ""

# Make a new environment interactively with create_configs script
new:
	python3 ../tools/create_configs.py
