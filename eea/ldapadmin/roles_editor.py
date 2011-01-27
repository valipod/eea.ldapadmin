from string import ascii_lowercase
import operator

from AccessControl import ClassSecurityInfo
from AccessControl.Permissions import view, view_management_screens
from App.class_init import InitializeClass
from OFS.Folder import Folder
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from persistent.mapping import PersistentMapping
from persistent.list import PersistentList

import ldap_agent
import ldap_config
from ui_common import load_template, SessionMessages, TemplateRenderer

eionet_edit_roles = 'Eionet edit roles'

manage_add_roles_editor_html = PageTemplateFile('zpt/roles_manage_add',
                                                globals())
manage_add_roles_editor_html.ldap_config_edit_macro = ldap_config.edit_macro
manage_add_roles_editor_html.config_defaults = lambda: ldap_config.defaults

def manage_add_roles_editor(parent, id, REQUEST=None):
    """ Create a new RolesEditor object """
    form = (REQUEST.form if REQUEST is not None else {})
    config = ldap_config.read_form(form)
    obj = RolesEditor(config)
    obj.title = form.get('title', id)
    obj._setId(id)
    parent._setObject(id, obj)

    if REQUEST is not None:
        REQUEST.RESPONSE.redirect(parent.absolute_url() + '/manage_workspace')

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

def filter_roles(agent, pattern):
    out = {}
    for role_id in agent.filter_roles(pattern):
        members = agent.members_in_role(role_id)
        # TODO catch individual errors when showing useres
        out[role_id] = {
            'users': [agent.user_info(user_id)
                      for user_id in members['users']],
            'orgs': [agent.org_info(org_id)
                     for org_id in members['orgs']],
        }
    return out

def filter_result_html(agent, pattern, renderer):
    _general_tmpl = load_template('zpt/roles_macros.zpt')
    options = {
        'pattern': pattern,
        'results': filter_roles(agent, pattern),
        'user_info_macro': _general_tmpl.macros['user-info'],
        'org_info_macro': _general_tmpl.macros['org-info'],
    }
    return renderer.render('zpt/roles_filter_result.zpt', **options)

class CommonTemplateLogic(object):
    def __init__(self, context):
        self.context = context

    def _get_request(self):
        return self.context.REQUEST

    def base_url(self):
        return self.context.absolute_url()

    def message_boxes(self):
        return SessionMessages(self._get_request(), SESSION_MESSAGES).html()

    def is_authenticated(self):
        return _is_authenticated(self._get_request())

    def role_parents_stack(self, role_id):
        return [(role_id, '?role_id=%s' % role_id)
                for role_id in _role_parents(role_id)]

    def breadcrumbs(self, stack):
        tr = self.context._render_template
        return tr.render('zpt/roles_breadcrumbs.zpt', stack=stack)

    def buttons_bar(self, current_page, role_id):
        options = {
            'current_page': current_page,
            'role_id': role_id,
            'common': self,
        }
        tr = self.context._render_template
        return tr.render('zpt/roles_buttons.zpt', **options)

    def search_roles_box(self, pattern=None):
        options = {
            'pattern': pattern,
            'predefined_filters': self.context._predefined_filters(),
        }
        tr = self.context._render_template
        return tr.render('zpt/roles_filter_form.zpt', **options)

    @property
    def macros(self):
        return load_template('zpt/roles_macros.zpt').macros


class RoleCreationError(Exception):
    def __init__(self, messages):
        self.messages = messages

import query

def role_members(agent, role_id):
    members = agent.members_in_role(role_id)
    return {
        'users': dict((user_id, agent.user_info(user_id))
                      for user_id in members['users']),
        'orgs': dict((org_id, agent.org_info(org_id))
                     for org_id in members['orgs']),
    }

class RolesEditor(Folder):
    meta_type = 'Eionet Roles Editor'
    security = ClassSecurityInfo()
    icon = '++resource++eea.ldapadmin-www/roles_editor.gif'

    meta_types = (
        {'name': query.Query.meta_type, 'action': 'manage_add_query_html'},
    )

    manage_options = Folder.manage_options[:2] + (
        {'label':'Configure', 'action':'manage_edit'},
    ) + Folder.manage_options[2:]

    _render_template = TemplateRenderer(CommonTemplateLogic)

    def __init__(self, config={}):
        super(RolesEditor, self).__init__()
        self._config = PersistentMapping(config)

    security.declareProtected(view_management_screens, 'get_config')
    def get_config(self):
        return dict(self._config)

    security.declareProtected(view_management_screens, 'manage_edit')
    manage_edit = PageTemplateFile('zpt/roles_manage_edit', globals())
    manage_edit.ldap_config_edit_macro = ldap_config.edit_macro

    security.declareProtected(view_management_screens, 'manage_edit_save')
    def manage_edit_save(self, REQUEST):
        """ save changes to configuration """
        self._config.update(ldap_config.read_form(REQUEST.form, edit=True))
        REQUEST.RESPONSE.redirect(self.absolute_url() + '/manage_edit')

    def _get_ldap_agent(self, bind=False):
        return ldap_config.ldap_agent_with_config(self._config, bind)

    def _predefined_filters(self):
        return sorted(self.objectValues([query.Query.meta_type]),
                      key=operator.methodcaller('getId'))

    security.declareProtected(view, 'index_html')
    def index_html(self, REQUEST):
        """ view """
        role_id = REQUEST.form.get('role_id', None)
        agent = self._get_ldap_agent()
        try:
            role_info = agent.role_info(role_id)
        except ldap_agent.RoleNotFound:
            REQUEST.RESPONSE.setStatus(404)
            options = {'message': "Role %s does not exist." % role_id}
            return self._render_template('zpt/generic_error.zpt', **options)

        options = {
            'role_id': role_id,
            'role_info': role_info,
            'role_names': agent.role_names_in_role(role_id),
            'role_members': role_members(agent, role_id),
            'can_edit': self.can_edit_roles(REQUEST.AUTHENTICATED_USER),
        }
        return self._render_template('zpt/roles_browse.zpt', **options)

    def _filter_results(self, pattern, title=None):
        search_url = self.absolute_url() + '/filter'
        options = {
            'pattern': pattern,
            'title': title,
            'breadcrumb_stack': [('Search', search_url)],
        }
        if pattern:
            agent = self._get_ldap_agent()
            results_html = filter_result_html(agent, pattern,
                                              self._render_template)
            options['results_html'] = results_html
            pattern_url = search_url + '?pattern:utf8:ustring=' + pattern
            options['breadcrumb_stack'] += [(pattern, pattern_url)]
        return self._render_template('zpt/roles_filter.zpt', **options)

    security.declareProtected(view, 'filter')
    def filter(self, REQUEST):
        """ view """
        pattern = REQUEST.form.get('pattern', '')
        return self._filter_results(pattern)

    security.declareProtected(view, 'can_edit_roles')
    def can_edit_roles(self, user):
        return bool(user.has_permission(eionet_edit_roles, self))

    security.declareProtected(eionet_edit_roles, 'create_role_html')
    def create_role_html(self, REQUEST):
        """ view """
        options = {
            'parent_id': REQUEST.form['parent_role_id'],
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

        agent = self._get_ldap_agent(bind=True)
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
        parent_role_id = REQUEST.form.get('parent_role_id', '') or None

        try:
            role_id = self._make_role(slug, parent_role_id, description)
        except RoleCreationError, e:
            for msg in e.messages:
                _set_session_message(REQUEST, 'error', msg)
            REQUEST.RESPONSE.redirect(self.absolute_url() +
                                      '/create_role_html?parent_role_id=' +
                                      (parent_role_id or ''))
            form_data = {'slug': slug, 'description': description}
            REQUEST.SESSION[SESSION_FORM_DATA] = form_data
        else:
            msg = u'Created role %s' % role_id
            if description:
                msg += u' "%s"' % description
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
            'role_id': role_id,
            'roles_to_remove': to_remove,
        }
        return self._render_template('zpt/roles_delete.zpt', **options)

    security.declareProtected(eionet_edit_roles, 'delete_role')
    def delete_role(self, REQUEST):
        """ remove a role and all its sub-roles """
        role_id = REQUEST.form['role_id']
        agent = self._get_ldap_agent(bind=True)
        agent.delete_role(role_id)
        parent_role_id = '-'.join(role_id.split('-')[:-1])
        _set_session_message(REQUEST, 'info', "Removed role %s" % role_id)
        rel_url = '/?role_id=' + parent_role_id if parent_role_id else '/'
        REQUEST.RESPONSE.redirect(self.absolute_url() + rel_url)

    security.declareProtected(eionet_edit_roles, 'add_member_html')
    def add_member_html(self, REQUEST):
        """ view """
        role_id = REQUEST.form['role_id']
        search_name = REQUEST.form.get('name', '')
        options = {
            'role_id': role_id,
            'search_name': search_name,
            'search_results': None,
        }
        if search_name:
            agent = self._get_ldap_agent()
            options['search_results'] = {
                'users': agent.search_user(search_name),
                'orgs': agent.search_org(search_name),
            }
        return self._render_template('zpt/roles_add_member.zpt', **options)

    security.declareProtected(eionet_edit_roles, 'add_user')
    def add_user(self, REQUEST):
        """ Add user `user_id` to role `role_id` """
        role_id = REQUEST.form['role_id']
        user_id = REQUEST.form['user_id']
        agent = self._get_ldap_agent(bind=True)
        role_id_list = agent.add_to_role(role_id, 'user', user_id)
        roles_msg = ', '.join(repr(r) for r in role_id_list)
        msg = "User %r added to roles %s." % (user_id, roles_msg)
        _set_session_message(REQUEST, 'info', msg)
        REQUEST.RESPONSE.redirect(self.absolute_url() + '/?role_id=' + role_id)

    security.declareProtected(eionet_edit_roles, 'add_org')
    def add_org(self, REQUEST):
        """ Add org `org_id` to role `role_id` """
        role_id = REQUEST.form['role_id']
        org_id = REQUEST.form['org_id']
        agent = self._get_ldap_agent(bind=True)
        role_id_list = agent.add_to_role(role_id, 'org', org_id)
        roles_msg = ', '.join(repr(r) for r in role_id_list)
        msg = "Organisation %r added to roles %s." % (org_id, roles_msg)
        _set_session_message(REQUEST, 'info', msg)
        REQUEST.RESPONSE.redirect(self.absolute_url() + '/?role_id=' + role_id)

    security.declareProtected(eionet_edit_roles, 'remove_members_html')
    def remove_members_html(self, REQUEST):
        """ Bulk-remove several members """
        role_id = REQUEST.form['role_id']
        agent = self._get_ldap_agent()
        options = {
            'role_id': role_id,
            'role_members': role_members(agent, role_id),
        }
        return self._render_template('zpt/roles_remove_members.zpt', **options)

    security.declareProtected(eionet_edit_roles, 'remove_members')
    def remove_members(self, REQUEST):
        """ Remove user several members from a role """
        role_id = REQUEST.form['role_id']
        user_id_list = REQUEST.form.get('user_id_list', [])
        org_id_list = REQUEST.form.get('org_id_list', [])
        assert type(user_id_list) is list
        assert type(org_id_list) is list

        agent = self._get_ldap_agent(bind=True)

        if user_id_list:
            for user_id in user_id_list:
                agent.remove_from_role(role_id, 'user', user_id)

            msg = "Users %r removed from role %r" % (user_id_list, role_id)
            _set_session_message(REQUEST, 'info', msg)

        if org_id_list:
            agent = self._get_ldap_agent(bind=True)
            for org_id in org_id_list:
                agent.remove_from_role(role_id, 'org', org_id)

            msg = ("Organisations %r removed from role %r" %
                   (org_id_list, role_id))
            _set_session_message(REQUEST, 'info', msg)

        REQUEST.RESPONSE.redirect(self.absolute_url()+'/?role_id='+role_id)

    security.declareProtected(eionet_edit_roles, 'remove_user_from_role_html')
    def remove_user_from_role_html(self, REQUEST):
        """ view """
        role_id = REQUEST.form['role_id']
        user_id = REQUEST.form['user_id']
        agent = self._get_ldap_agent()
        user_roles = agent.list_member_roles('user', user_id)
        options = {
            'role_id': role_id,
            'user_id': user_id,
            'role_id_list': sorted(r for r in user_roles
                                   if agent.is_subrole(r, role_id)),
        }

        return self._render_template('zpt/roles_remove_user.zpt', **options)

    security.declareProtected(eionet_edit_roles, 'remove_user_from_role')
    def remove_user_from_role(self, REQUEST):
        """ Remove a single user from the role """
        role_id = REQUEST.form['role_id']
        user_id = REQUEST.form['user_id']

        agent = self._get_ldap_agent(bind=True)
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
            'search_name': search_name,
            'user_id': user_id,
        }

        if search_name:
            agent = self._get_ldap_agent()
            options['search_results'] = agent.search_user(search_name)

        if user_id is not None:
            agent = self._get_ldap_agent()
            options['user_roles'] = agent.list_member_roles('user', user_id)

        return self._render_template('zpt/roles_search_users.zpt', **options)

    security.declareProtected(view_management_screens, 'manage_add_query_html')
    manage_add_query_html = query.manage_add_query_html

    security.declareProtected(view_management_screens, 'manage_add_query')
    manage_add_query = query.manage_add_query

InitializeClass(RolesEditor)
