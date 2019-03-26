from seneca.libs.storage.datatypes import Hash

# Declare Data Types
app_checks = Hash('application_checks', default_value=0)

@export
def run_contract(user, link):
    # assert link is a valid link
    app_checks['name_check'] = True if (link.name.first == user.first) and (link.name.last == user.last) else False
    app_checks['signature_check'] = True if link.signature else False
    app_checks['address_check'] = True if link.address else False
    status = True if app_checks['name_check'] and app_checks['signature_check'] and app_checks['address_check'] else False
    return status

