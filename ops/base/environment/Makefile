# Set the root of cilantro tobe immutable regardless of where the makefile is called from
MY_PATH ?= $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
CILANTRO_ROOT ?= $(join $(MY_PATH), ../../../)

DOCKER_TAG ?= $(shell bash $(CILANTRO_ROOT)/ops/tools/generate_tag.sh)

test:
	echo $(MY_PATH)
	echo $(CILANTRO_ROOT)
	echo $(shell basename $(MY_PATH))

run: buildpush
	@terraform apply -var 'docker_tag=$(DOCKER_TAG)' -var 'user=$(USER)' -var 'environment_name=$(shell basename $(MY_PATH))'

buildpush:
	@bash $(CILANTRO_ROOT)/ops/tools/docker_build_push.sh --push

clean: destroy

destroy:
	@terraform destroy -var 'docker_tag=$(DOCKER_TAG)' -var 'user=$(USER)' -var 'environment_name=$(shell basename $(MY_PATH))'
