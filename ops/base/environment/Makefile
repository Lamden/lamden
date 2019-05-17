.PHONY: run restart buildpush apply

# Set the root of cilantro_ee tobe immutable regardless of where the makefile is called from
MY_PATH ?= $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
CILANTRO_ROOT ?= $(join $(MY_PATH), ../../../)

# Restrict the parallelism to the minimum necessary for proper launch due to bugs with too much parallel SSH
NODE_COUNT ?= $(shell find $(MY_PATH)conf/* -maxdepth 0 -type d | wc -l | sed 's/^ *//;s/ *$$//')
PARALLELISM ?= $(shell if [ "$(NODE_COUNT)" -gt "10" ]; then echo "-parallelism=$(NODE_COUNT)"; else echo ""; fi)

ADDITIONAL_FLAGS ?= 

RESOURCE ?=

# Resolve the tag using the tag resolver script, this is the default
DOCKER_TAG ?= $(shell bash $(CILANTRO_ROOT)/ops/tools/generate_tag.sh)

help:
	@echo ""
	@echo "==============================================="
	@echo "|| Cilantro DevOps environment Makefile help ||"
	@echo "==============================================="
	@echo ""
	@echo "Common use-case examples:"
	@echo "========================="
	@echo " -- make run"
	@echo "     Do a full buildpush + apply"
	@echo " -- ADDITIONAL_FLAGS='-auto-approve' make run"
	@echo "     Auto approve the terraform changes during a make run (NOTE: this will not"
	@echo "     give you the chance to validate your changes and thus should not be used for"
	@echo "     production instances"
	@echo " -- make restart"
	@echo "     Restart with last docker tag that completed the apply stage"
	@echo " -- DOCKER_TAG=<tag> make apply"
	@echo "     Run with a specifically provided tag (NOTE: if you are running this command"
	@echo "     with the same tag as the last run, it will not restart docker)"
	@echo " -- make show"
	@echo "     Show the outputs from the provisioning step. Including SSH commands"
	@echo ""
	@echo "Running Tests"
	@echo "============="
	@echo "NOTE: when running test endpoints, please be sure you have a deployment for the"
	@echo "      current environment active first. This can be accomplished with a call to"
	@echo "      'make run'"
	@echo " -- make testdump"
	@echo "	    Start a black-box test to dump transactions to the deployed environment"
	@echo " -- make testcurr"
	@echo "     Run end-to-end black-box test on the currency contract"
	@echo " -- make testsc"
	@echo "     Run end-to-end black-box test on smart contracts in general"
	@echo ""
	@echo "All Available Targets:"
	@echo "======================"
	@echo " -- make run             Do a full docker build + docker push (of latest code local)"
	@echo "                         then terraform apply"
	@echo " -- make restart         Taint all the docker containers so they are restarted, use"
	@echo "                         the tag from the last known successful launch"
	@echo " -- make buildpush       Build and push the docker container with a tag representing"
	@echo "                         the branch + commit + code hash"
	@echo " -- make apply           Run the terraform apply steps to change provisioned"
	@echo "                         resources to match any changes locally"
	@echo " -- make getlasttag      Get the tag from the last known successful launch"
	@echo " -- make taintdocker     Taint all the docker containers so they are rebooted on the"
	@echo "                         next run of 'make apply'"
	@echo " -- make clean           Clean out the cache files, destroy the provisioned terraform"
	@echo "                         resources"
	@echo " -- make destroy         Destroy the provisioned terraform resources"
	@echo " -- make show            Show the outputs from the provisioning"
	@echo " -- make testdump        Start a test script to dump transactions to the deployed"
	@echo "                         environment"
	@echo " -- make testcurr        End-to-End black box, programatically test the currency"
	@echo "                         contract"
	@echo " -- make testsc          End-to-End black box, programatically test submitting a smart contract"
	@echo "                         and transacting upon it"
	@echo ""


# Do a full run including a buildpush call
run: buildpush apply

# Restart the instances with the last known tag (force)
# This target contains some tricky logic to find all the docker resources in terraform and taint them so they are rerun
# If you are looking to restart your nodes with the last successful tag, USE THIS
restart: getlasttag taintdocker apply

# Build the containers and push the image
buildpush:
	@bash $(CILANTRO_ROOT)/ops/tools/docker_build_push.sh --push

# Run the necessary terraform application process
apply:
	@rm $(MY_PATH).cache/ip_* || true
	@echo "Applying with tag=$(DOCKER_TAG) user=$(USER) environment_name=$(shell basename $(MY_PATH)) flags='$(PARALLELISM) $(ADDITIONAL_FLAGS)'"
	terraform apply -var 'docker_tag=$(DOCKER_TAG)' -var 'user=$(USER)' -var 'environment_name=$(shell basename $(MY_PATH))' $(PARALLELISM) $(ADDITIONAL_FLAGS)
	@echo "$(DOCKER_TAG)" > $(MY_PATH).cache/docker_tag

# Get the docker_tag of the last successful run from the .cache. Error out if not able to find
getlasttag:
	$(eval DOCKER_TAG := $(shell cat $(MY_PATH).cache/docker_tag))
	if [ "$(DOCKER_TAG)" = "" ]; then echo "ERROR: Docker tag not found in cache, if this is the first time you are running this environment, please use 'make run'"; exit 1; fi

taintdocker:
	@while read -r line; do bash -c "$$line"; done <<< "$$(terraform show | grep null_resource\.docker | sed 's/.$$//' | cut -d'.' -f 2 | awk '{print "terraform taint -module="$$1" null_resource.docker"}')"

taint:
	@while read -r line; do bash -c "$$line"; done <<< "$$(terraform show | grep null_resource\.docker | sed 's/.$$//' | cut -d'.' -f 2 | awk '{print "terraform taint -module="$$1" $(RESOURCE)"}')"


# Prototypical naming scheme for cleaning up, maps to terraform naming scheme of 'destroy'
clean: destroy
	@rm -rf $(MY_PATH).cache/*

# Destroy all the terraform resources
destroy:
	@terraform destroy -var 'docker_tag=$(DOCKER_TAG)' -var 'user=$(USER)' -var 'environment_name=$(shell basename $(MY_PATH))' $(ADDITIONAL_FLAGS)

# Show all the outputs from the run
show:
	@echo ""
	@echo "============="
	@echo "|| OUTPUTS ||"
	@echo "============="
	@echo ""
	@terraform output | sed -nE "s/-ssh//p" | sed -nE "s/ = (.*)/,\1,/p" | tr ',' '\n'
	@echo ""

testdump:
	@python3 $(CILANTRO_ROOT)/ops/tools/dump.py $(MY_PATH)


testcurr:
	@python3 $(CILANTRO_ROOT)/ops/tools/test_end_to_end.py $(MY_PATH)

testsc:
	@python3 $(CILANTRO_ROOT)/ops/tools/test_smart_contract_submit.py $(MY_PATH)
