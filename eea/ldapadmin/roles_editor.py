from string import ascii_lowercase

from AccessControl import ClassSecurityInfo
from AccessControl.Permissions import view, view_management_screens
from Globals import InitializeClass
from OFS.Folder import Folder
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from persistent.mapping import PersistentMapping
from persistent.list import PersistentList

from ldap_agent import LdapAgent
from query import Query, manage_add_query, manage_add_query_html

eionet_edit_roles = 'Eionet edit roles'

manage_add_editor_html = PageTemplateFile('zpt/editor_manage_add', globals())
manage_add_editor_html.properties_form_fields = lambda: \
    RolesEditor.manage_edit.pt_macros()['properties_form_fields']

def manage_add_editor(parent, id, REQUEST=None):
    """ Create a new RolesEditor object """
    if REQUEST is not None:
        config = REQUEST.form
    else:
        config = {}
    obj = RolesEditor(config)
    obj.title = config.get('title', id)
    obj.ldap_server = 'ldap2.eionet.europa.eu'
    obj._setId(id)
    parent._setObject(id, obj)

    if REQUEST is not None:
        url = parent.absolute_url() + '/manage_workspace'
        return REQUEST.RESPONSE.redirect(url)

def _get_session_messages(request):
    session = request.SESSION
    if 'messages' not in session.keys():
        session['messages'] = PersistentList()
    return session['messages']

class RolesEditor(Folder):
    meta_type = 'Eionet Roles Editor'
    security = ClassSecurityInfo()
    icon = 'misc_/EionetRolesEditor/roles_editor.gif'

    meta_types = (
        {'name': Query.meta_type, 'action': 'manage_add_query_html'},
    )

    manage_options = Folder.manage_options[:2] + (
        {'label':'Configure', 'action':'manage_edit'},
    ) + Folder.manage_options[2:]

    security.declareProtected(view_management_screens, 'get_config')
    def get_config(self):
        return dict(self.config)

    def __init__(self, config):
        super(RolesEditor, self).__init__()
        self.config = PersistentMapping({
            'login_dn': config.get('login_dn', ''),
            'login_pw': config.get('login_pw', ''),
            'ldap_server': config.get('ldap_server', ''),
            'users_dn': config.get('users_dn', ''),
            'orgs_dn': config.get('orgs_dn', ''),
            'roles_dn': config.get('roles_dn', ''),
        })

    security.declareProtected(view, 'general_tmpl')
    general_tmpl = PageTemplateFile('zpt/editor_general_tmpl', globals())

    security.declareProtected(view_management_screens, 'manage_edit')
    manage_edit = PageTemplateFile('zpt/editor_manage_edit', globals())

    security.declareProtected(view_management_screens, 'manage_edit_save')
    def manage_edit_save(self, REQUEST):
        """ save changes to configuration """
        self.config.update({
            'login_dn': REQUEST.form['login_dn'],
            'ldap_server': REQUEST.form['ldap_server'],
            'users_dn': REQUEST.form['users_dn'],
            'orgs_dn': REQUEST.form['orgs_dn'],
            'roles_dn': REQUEST.form['roles_dn'],
        })
        if REQUEST.form['login_pw']:
            self.config['login_pw'] = REQUEST.form['login_pw']

        REQUEST.RESPONSE.redirect(self.absolute_url() + '/manage_edit')

    def _login_data(self):
        return (self.config['login_dn'], self.config['login_pw'])

    security.declareProtected(view, 'index_html')
    index_html = PageTemplateFile('zpt/editor_browse', globals())

    messages_box = PageTemplateFile('zpt/messages_box', globals())

    security.declarePrivate('add_message')
    def add_message(self, msg):
        _get_session_messages(self.REQUEST).append(msg)

    security.declareProtected(view, 'get_messages')
    def get_messages(self):
        messages = _get_session_messages(self.REQUEST)
        messages_list = list(messages)
        messages[:] = []
        return messages_list

    security.declareProtected(view, 'get_ldap_agent')
    def get_ldap_agent(self):
        return Zope2LdapAgent(**dict(self.config)).__of__(self)

    filter = PageTemplateFile('zpt/editor_filter', globals())

    security.declareProtected(view, 'can_edit_roles')
    def can_edit_roles(self, user):
        return bool(user.has_permission(eionet_edit_roles, self))

    security.declareProtected(eionet_edit_roles, 'create_role')
    create_role = PageTemplateFile('zpt/editor_create_role', globals())

    security.declareProtected(eionet_edit_roles, 'do_create_role')
    def do_create_role(self, RESPONSE,
                    role_id_frag, description, parent_role_id=None):
        """ add a role """
        assert isinstance(role_id_frag, basestring)
        for ch in role_id_frag:
            assert ch in ascii_lowercase

        if parent_role_id is None:
            role_id = role_id_frag
        else:
            role_id = parent_role_id + '-' + role_id_frag
        agent = self.get_ldap_agent()
        agent.perform_bind(*self._login_data())
        agent.create_role(role_id, description)
        self.add_message("Created role %s %r" % (role_id, description))
        RESPONSE.redirect(self.absolute_url() + '/?role_id=' + role_id)

    _delete_role = PageTemplateFile('zpt/editor_delete_role', globals())
    security.declareProtected(eionet_edit_roles, 'delete_role')
    def delete_role(self, REQUEST, role_id):
        """ remove a role and all its sub-roles """
        agent = self.get_ldap_agent()

        if REQUEST.form.get('confirm', 'no') == 'yes':
            agent.perform_bind(*self._login_data())
            agent.delete_role(role_id)
            parent_role_id = '-'.join(role_id.split('-')[:-1])
            self.add_message("Removed role %s" % role_id)
            REQUEST.RESPONSE.redirect(self.absolute_url() +
                                      '/?role_id=' + parent_role_id)

        else:
            to_remove = map(agent._role_id, agent._sub_roles(role_id))
            return self._delete_role(roles_to_remove=to_remove,
                                     role_id=role_id)

    security.declareProtected(eionet_edit_roles, 'search_by_name')
    def search_by_name(self, name):
        return self.get_ldap_agent().search_by_name(name)

    security.declareProtected(eionet_edit_roles, 'add_to_role')
    add_to_role = PageTemplateFile('zpt/editor_add_to_role', globals())

    security.declareProtected(eionet_edit_roles, 'do_add_to_role')
    def do_add_to_role(self, RESPONSE, role_id, user_id):
        """ Add user `user_id` to role `role_id` """
        agent = self.get_ldap_agent()
        agent.perform_bind(*self._login_data())
        agent.add_to_role(role_id, 'user', user_id)
        self.add_message("User %r added to role %r" % (user_id, role_id))
        RESPONSE.redirect(self.absolute_url() + '/?role_id=' + role_id)

    _remove_from_role_html = PageTemplateFile('zpt/editor_remove_from_role',
                                              globals())
    security.declareProtected(eionet_edit_roles, 'remove_from_role')
    def remove_from_role(self, REQUEST, role_id, user_id_list):
        """ Remove user `user_id` from role `role_id` """
        agent = self.get_ldap_agent()

        if REQUEST.form.get('confirm', 'no') == 'yes':
            agent.perform_bind(*self._login_data())
            for user_id in user_id_list:
                agent.remove_from_role(role_id, 'user', user_id)
            self.add_message("Users %r removed from role %r" %
                             (user_id_list, role_id))

            redirect_default = self.absolute_url()+'/?role_id='+role_id
            REQUEST.RESPONSE.redirect(REQUEST.form.get('redirect_to',
                                                       redirect_default))

        else:
            return self._remove_from_role_html()

    security.declareProtected(eionet_edit_roles, 'search_users')
    search_users = PageTemplateFile('zpt/editor_search_users', globals())

    security.declareProtected(eionet_edit_roles, 'list_user_roles')
    def list_user_roles(self, user_id):
        return self.get_ldap_agent().list_member_roles('user', user_id)

    security.declareProtected(view_management_screens, 'manage_add_query_html')
    manage_add_query_html = manage_add_query_html

    security.declareProtected(view_management_screens, 'manage_add_query')
    manage_add_query = manage_add_query

    def get_roles_editor(self):
        return self


from Acquisition import Implicit
class Zope2LdapAgent(Implicit, LdapAgent):
    security = ClassSecurityInfo()
    for name in ('role_names_in_role', 'filter_roles', 'members_in_role',
                 'user_info', 'org_info', 'role_info'):
        security.declareProtected(view, name)
InitializeClass(Zope2LdapAgent)
