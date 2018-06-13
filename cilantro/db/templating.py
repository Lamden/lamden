import os


def _read_templates() -> dict:
    def _get_template_name(filename):
        parts = filename.split('.')

        assert len(parts) == 2, "Expected a template file of format some_name.template but instead got {}".format(
            filename)
        assert parts[1] == 'template', "Expected a template file with extension .template but got filename {}".format(
            filename)

        return parts[0]

    path = os.path.abspath(__file__)
    dir_path = os.path.dirname(path)
    templates_dir = "{}/../contracts/templates".format(dir_path)

    templates = {}

    for filename in sorted(os.listdir(templates_dir)):
        with open("{}/{}".format(templates_dir, filename), 'r') as f:
            template_str = f.read()
            template_name = _get_template_name(filename)

            templates[template_name] = template_str

    return templates


templates = _read_templates()


class ContractTemplate:

    @staticmethod
    def interpolate_template(template_name, **kwargs) -> str:
        """
        Generates smart contract code using the templates in contracts/templates. This works by creating placeholder
        variables in the template files using the syntax '{__some_arg__}'. Wrapping the variable 'some_arg' with a
        curly bracket and double underscore signifies a placeholder for a variable named 'some_arg'. This function will
        then look for a variable of the same name in kwargs, and replace the placeholder with the specified value. For
        example passing in some_arg=10 will replace all occurrences of '{__some_arg__}' in the template and return
        this interpolated code.

        :param template_name: The name of the template to use. Must be the name of the file in cilantro/contracts/templates
        (without the .template extension)
        extension)
        :param kwargs: Arguements to interpolate in the template. See docstring above on how to use this.
        :return: A string representing the template code with kwargs interpolated
        """
        assert template_name in templates, "No template named {} found in templates {}".format(template_name, templates.keys())
        code_str = templates[template_name]

        for arg in kwargs:
            placeholder = _placeholder_for_arg(arg)
            assert code_str.count(placeholder) > 0, "No placeholder(s) named {} found for template named {}"\
                                                    .format(placeholder, template_name)

            code_str = code_str.replace(placeholder, kwargs[arg])

        # TODO sanity check to ensure ALL placeholders were interpolated (maybe just ask falc supply some lit regex)

        return code_str


def _placeholder_for_arg(arg_name: str) -> str:
    return '{__' + arg_name + '__}'
