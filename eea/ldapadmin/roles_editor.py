from string import ascii_lowercase

from AccessControl import ClassSecurityInfo
from AccessControl.Permissions import view, view_management_screens
from App.class_init import InitializeClass
from OFS.Folder import Folder
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from persistent.mapping import PersistentMapping
from persistent.list import PersistentList

from ldap_agent import LdapAgent
from query import Query, manage_add_query, manage_add_query_html
from ui_common import load_template, SessionMessages, Zope3TemplateInZope2

eionet_edit_roles = 'Eionet edit roles'

manage_add_editor_html = PageTemplateFile('zpt/roles_manage_add', globals())
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

def _is_authenticated(request):
    return ('Authenticated' in request.AUTHENTICATED_USER.getRoles())

def _role_parents(role_id):
    if role_id is None:
        return []
    parents = [role_id]
    while '-' in role_id:
        role_id = role_id.rsplit('-', 1)[0]
        parents.append(role_id)
    return reversed(parents)

SESSION_PREFIX = 'eea.ldapadmin.roles_editor'
SESSION_MESSAGES = SESSION_PREFIX + '.messages'
SESSION_FORM_DATA = SESSION_PREFIX + '.form_data'

def _set_session_message(request, msg_type, msg):
    SessionMessages(request, SESSION_MESSAGES).add(msg_type, msg)

def _session_messages_html(request):
    return SessionMessages(request, SESSION_MESSAGES).html()

def buttons_bar(base_url, current):
    tmpl = load_template('zpt/roles_buttons.zpt')
    return tmpl(base_url=base_url, current=current)

def filter_roles(agent, pattern):
    out = {}
    for role_id in agent.filter_roles(pattern):
        members = agent.members_in_role(role_id)
        # TODO catch individual errors when showing useres
        out[role_id] = {
            'users': [agent.user_info(user_id)
                      for user_id in members['users']],
            'orgs': [],
        }
    return out

def filter_result_html(agent, pattern, is_authenticated):
    _general_tmpl = load_template('zpt/roles_macros.zpt')
    options = {
        'is_authenticated': is_authenticated,
        'pattern': pattern,
        'results': filter_roles(agent, pattern),
        'user_info_macro': _general_tmpl.macros['user-info'],
        'org_info_macro': _general_tmpl.macros['org-info'],
    }
    return load_template('zpt/roles_filter_result.zpt')(**options)


class RoleCreationError(Exception):
    def __init__(self, messages):
        self.messages = messages

class RolesEditor(Folder):
    meta_type = 'Eionet Roles Editor'
    security = ClassSecurityInfo()
    icon = '++resource++eea.ldapadmin-roles_editor.gif'

    meta_types = (
        {'name': Query.meta_type, 'action': 'manage_add_query_html'},
    )

    manage_options = Folder.manage_options[:2] + (
        {'label':'Configure', 'action':'manage_edit'},
    ) + Folder.manage_options[2:]

    _render_template = Zope3TemplateInZope2()

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
    general_tmpl = PageTemplateFile('zpt/roles_macros', globals())

    security.declareProtected(view_management_screens, 'manage_edit')
    manage_edit = PageTemplateFile('zpt/roles_manage_edit', globals())

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
    def index_html(self, REQUEST):
        """ view """
        role_id = REQUEST.form.get('role_id', None)
        agent = self._get_ldap_agent()
        user_ids = agent.members_in_role(role_id)['users']
        _general_tmpl = load_template('zpt/roles_macros.zpt')
        options = {
            'base_url': self.absolute_url(),
            'role_id': role_id,
            'role_info': agent.role_info(role_id),
            'role_names': agent.role_names_in_role(role_id),
            'role_parents': _role_parents(role_id),
            'role_members': {
                'users': dict((user_id, agent.user_info(user_id))
                              for user_id in user_ids),
                'orgs': {},
            },
            'can_edit': self.can_edit_roles(REQUEST.AUTHENTICATED_USER),
            'is_authenticated': _is_authenticated(REQUEST),
            'user_info_macro': _general_tmpl.macros['user-info'],
            'org_info_macro': _general_tmpl.macros['org-info'],
            'messages_html': _session_messages_html(REQUEST),
            'buttons_html': buttons_bar(self.absolute_url(), 'browse'),
        }
        return self._render_template('zpt/roles_browse.zpt', **options)

    def messages_box(self):
        return _session_messages_html(self.REQUEST)

    security.declarePrivate('add_message')
    def add_message(self, msg):
        _set_session_message(self.REQUEST, 'info', msg)

    security.declareProtected(view, 'get_ldap_agent')
    def get_ldap_agent(self):
        # deprecated; templates have no business talking to the LDAP agent
        return Zope2LdapAgent(**dict(self.config)).__of__(self)

    def _get_ldap_agent(self):
        return LdapAgent(**dict(self.config))

    security.declareProtected(view, 'filter')
    def filter(self, REQUEST):
        """ view """
        pattern = REQUEST.form.get('pattern', '')
        options = {
            'pattern': pattern,
            'buttons_html': buttons_bar(self.absolute_url(), 'filter'),
        }
        if pattern:
            agent = self._get_ldap_agent()
            is_authenticated = _is_authenticated(REQUEST)
            results_html = filter_result_html(agent, pattern, is_authenticated)
            options['results_html'] = results_html
        return self._render_template('zpt/roles_filter.zpt', **options)

    security.declareProtected(view, 'can_edit_roles')
    def can_edit_roles(self, user):
        return bool(user.has_permission(eionet_edit_roles, self))

    security.declareProtected(eionet_edit_roles, 'create_role_html')
    def create_role_html(self, REQUEST):
        """ view """
        options = {
            'base_url': self.absolute_url(),
            'parent_id': REQUEST.form['parent_role_id'],
            'buttons_html': buttons_bar(self.absolute_url(), 'browse'),
            'messages_html': _session_messages_html(REQUEST),
        }
        session = REQUEST.SESSION
        if SESSION_FORM_DATA in session.keys():
            options['form_data'] = session[SESSION_FORM_DATA]
            del session[SESSION_FORM_DATA]
        return self._render_template('zpt/roles_create.zpt', **options)

    def _make_role(self, slug, parent_role_id, description):
        assert isinstance(slug, basestring)
        if not slug:
            raise RoleCreationError(["Role name is required."])
        for ch in slug:
            if ch not in ascii_lowercase:
                msg = ("Invalid role name, it must contain only lowercase "
                       "latin letters.")
                raise RoleCreationError([msg])

        if parent_role_id is None:
            role_id = slug
        else:
            role_id = parent_role_id + '-' + slug

        agent = self._get_ldap_agent()
        agent.perform_bind(*self._login_data())
        try:
            agent.create_role(str(role_id), description)
        except ValueError, e:
            msg = unicode(e)
            if 'DN already exists' in msg:
                msg = 'Role "%s" already exists.' % slug
            raise RoleCreationError([msg])

        return role_id

    security.declareProtected(eionet_edit_roles, 'create_role')
    def create_role(self, REQUEST):
        """ add a role """
        slug = REQUEST.form['slug']
        description = REQUEST.form['description']
        parent_role_id = REQUEST.form.get('parent_role_id', None)

        try:
            role_id = self._make_role(slug, parent_role_id, description)
        except RoleCreationError, e:
            for msg in e.messages:
                _set_session_message(REQUEST, 'error', msg)
            REQUEST.RESPONSE.redirect(self.absolute_url() +
                                      '/create_role_html?parent_role_id=' +
                                      parent_role_id)
            form_data = {'slug': slug, 'description': description}
            REQUEST.SESSION[SESSION_FORM_DATA] = form_data
        else:
            msg = "Created role %s %r" % (role_id, description)
            _set_session_message(REQUEST, 'info', msg)
            REQUEST.RESPONSE.redirect(self.absolute_url() +
                                      '/?role_id=' + role_id)

    security.declareProtected(eionet_edit_roles, 'delete_role_html')
    def delete_role_html(self, REQUEST):
        """ view """
        role_id = REQUEST.form['role_id']
        agent = self._get_ldap_agent()

        to_remove = map(agent._role_id, agent._sub_roles(role_id))
        options = {
            'base_url': self.absolute_url(),
            'role_id': role_id,
            'roles_to_remove': to_remove,
            'buttons_html': buttons_bar(self.absolute_url(), 'browse'),
        }
        return self._render_template('zpt/roles_delete.zpt', **options)

    security.declareProtected(eionet_edit_roles, 'delete_role')
    def delete_role(self, REQUEST):
        """ remove a role and all its sub-roles """
        role_id = REQUEST.form['role_id']
        agent = self._get_ldap_agent()

        agent.perform_bind(*self._login_data())
        agent.delete_role(role_id)
        parent_role_id = '-'.join(role_id.split('-')[:-1])
        _set_session_message(REQUEST, 'info', "Removed role %s" % role_id)
        REQUEST.RESPONSE.redirect(self.absolute_url() +
                                  '/?role_id=' + parent_role_id)


    security.declareProtected(eionet_edit_roles, 'add_to_role_html')
    def add_to_role_html(self, REQUEST):
        """ view """
        role_id = REQUEST.form['role_id']
        search_name = REQUEST.form.get('name', '')
        if search_name:
            search_results = self._get_ldap_agent().search_by_name(search_name)
        else:
            search_results = []
        _general_tmpl = load_template('zpt/roles_macros.zpt')
        options = {
            'base_url': self.absolute_url(),
            'role_id': role_id,
            'search_name': search_name,
            'search_results': search_results,
            'user_info_macro': _general_tmpl.macros['user-info'],
            'buttons_html': buttons_bar(self.absolute_url(), 'browse'),
        }
        return self._render_template('zpt/roles_add_user.zpt', **options)

    security.declareProtected(eionet_edit_roles, 'add_to_role')
    def add_to_role(self, REQUEST):
        """ Add user `user_id` to role `role_id` """
        role_id = REQUEST.form['role_id']
        user_id = REQUEST.form['user_id']
        agent = self._get_ldap_agent()
        agent.perform_bind(*self._login_data())
        role_id_list = agent.add_to_role(role_id, 'user', user_id)
        roles_msg = ', '.join(repr(r) for r in role_id_list)
        msg = "User %r added to roles %s." % (user_id, roles_msg)
        _set_session_message(REQUEST, 'info', msg)
        REQUEST.RESPONSE.redirect(self.absolute_url() + '/?role_id=' + role_id)

    security.declareProtected(eionet_edit_roles, 'remove_from_role')
    def remove_from_role(self, REQUEST):
        """ Remove user several users from a role """
        role_id = REQUEST.form['role_id']
        user_id_list = REQUEST.form.get('user_id_list', [])
        assert type(user_id_list) is list

        if user_id_list:
            agent = self._get_ldap_agent()
            agent.perform_bind(*self._login_data())
            for user_id in user_id_list:
                agent.remove_from_role(role_id, 'user', user_id)

            msg = "Users %r removed from role %r" % (user_id_list, role_id)
            _set_session_message(REQUEST, 'info', msg)

        redirect_default = self.absolute_url()+'/?role_id='+role_id
        REQUEST.RESPONSE.redirect(REQUEST.form.get('redirect_to',
                                                   redirect_default))

    security.declareProtected(eionet_edit_roles, 'remove_user_from_role_html')
    def remove_user_from_role_html(self, REQUEST):
        """ view """
        role_id = REQUEST.form['role_id']
        user_id = REQUEST.form['user_id']
        agent = self._get_ldap_agent()
        options = {
            'base_url': self.absolute_url(),
            'role_id': role_id,
            'user_id': user_id,
            'role_id_list': self._subroles_of_user(user_id, role_id, agent),
            'buttons_html': buttons_bar(self.absolute_url(), 'search'),
        }

        return self._render_template('zpt/roles_remove_user.zpt', **options)

    def _subroles_of_user(self, user_id, role_id, agent):
        # TODO _sub_roles needs to have its own nice API in LdapAgent
        user_roles = agent.list_member_roles('user', user_id)
        sub_roles = map(agent._role_id, agent._sub_roles(role_id))
        return sorted(set(user_roles) & set(sub_roles))

    security.declareProtected(eionet_edit_roles, 'remove_user_from_role')
    def remove_user_from_role(self, REQUEST):
        """ Remove a single user from the role """
        role_id = REQUEST.form['role_id']
        user_id = REQUEST.form['user_id']

        agent = self._get_ldap_agent()
        agent.perform_bind(*self._login_data())
        role_id_list = agent.remove_from_role(role_id, 'user', user_id)

        roles_msg = ', '.join(repr(r) for r in role_id_list)
        msg = "User %r removed from roles %s." % (user_id, roles_msg)
        _set_session_message(REQUEST, 'info', msg)

        REQUEST.RESPONSE.redirect(self.absolute_url() +
                                  '/search_users?user_id=' + user_id)

    security.declareProtected(eionet_edit_roles, 'search_users')
    def search_users(self, REQUEST):
        """ view """
        search_name = REQUEST.form.get('name', '')
        user_id = REQUEST.form.get('user_id', None)
        options = {
            'base_url': self.absolute_url(),
            'search_name': search_name,
            'user_id': user_id,
            'messages_html': _session_messages_html(REQUEST),
            'buttons_html': buttons_bar(self.absolute_url(), 'search'),
        }

        if search_name:
            agent = self._get_ldap_agent()
            options['search_results'] = agent.search_by_name(search_name)
            _general_tmpl = load_template('zpt/roles_macros.zpt')
            options['user_info_macro'] = _general_tmpl.macros['user-info']

        if user_id is not None:
            agent = self._get_ldap_agent()
            options['user_roles'] = agent.list_member_roles('user', user_id)

        return self._render_template('zpt/roles_search_users.zpt', **options)

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
