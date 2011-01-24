from ui_common import load_template
from ldap_agent import LdapAgent

defaults = {
    'admin_dn': "uid=_admin,ou=Users,o=EIONET,l=Europe",
    'admin_pw': "",
    'ldap_server': "ldap2.eionet.europa.eu",
    'users_dn': "ou=Users,o=EIONET,l=Europe",
    'orgs_dn': "ou=Organisations,o=EIONET,l=Europe",
    'roles_dn': "ou=Roles,o=EIONET,l=Europe",
}

def read_form(form, edit=False):
    config = dict((name, form.get(name, default))
                  for name, default in defaults.iteritems())
    if edit:
        if not config['admin_pw']:
            del config['admin_pw']
    return config

def ldap_agent_with_config(config, bind=False):
    agent = LdapAgent(ldap_server=config['ldap_server'],
                      users_dn=config['users_dn'],
                      orgs_dn=config['orgs_dn'],
                      roles_dn=config['roles_dn'])
    if bind:
        agent.perform_bind(config['admin_dn'],
                           config['admin_pw'])
    return agent

edit_macro = load_template('zpt/ldap_config.zpt').macros['edit']
