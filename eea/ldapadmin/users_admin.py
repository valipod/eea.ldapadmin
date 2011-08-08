from AccessControl import ClassSecurityInfo
from App.class_init import InitializeClass
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from OFS.SimpleItem import SimpleItem
from OFS.PropertyManager import PropertyManager
from AccessControl.Permissions import view, view_management_screens
from persistent.mapping import PersistentMapping

import ldap_config
from ui_common import SessionMessages, TemplateRenderer

import deform
from eea import usersdb


user_info_schema = usersdb.user_info_schema.clone()
user_info_schema['postal_address'].widget = deform.widget.TextAreaWidget()


eionet_edit_users = 'Eionet edit users'

manage_add_users_admin_html = PageTemplateFile('zpt/users_manage_add',
                                                globals())
manage_add_users_admin_html.ldap_config_edit_macro = ldap_config.edit_macro
manage_add_users_admin_html.config_defaults = lambda: ldap_config.defaults

def manage_add_users_admin(parent, id, REQUEST=None):
    """ Create a new UsersAdmin object """
    if REQUEST is not None:
        form = REQUEST.form
    else:
        form = {}
    config = ldap_config.read_form(form)
    obj = UsersAdmin(config)
    obj.title = form.get('title', id)
    obj._setId(id)
    parent._setObject(id, obj)

    if REQUEST is not None:
        REQUEST.RESPONSE.redirect(parent.absolute_url() + '/manage_workspace')

def _is_authenticated(request):
    return ('Authenticated' in request.AUTHENTICATED_USER.getRoles())

SESSION_PREFIX = 'eea.ldapadmin.users_admin'
SESSION_MESSAGES = SESSION_PREFIX + '.messages'
SESSION_FORM_DATA = SESSION_PREFIX + '.form_data'

def _set_session_message(request, msg_type, msg):
    SessionMessages(request, SESSION_MESSAGES).add(msg_type, msg)


class CommonTemplateLogic(object):
    def __init__(self, context):
        self.context = context

    def base_url(self):
        return self.context.absolute_url()

    def message_boxes(self):
        return SessionMessages(self.context.REQUEST, SESSION_MESSAGES).html()


# this class should be called UsersEditor, similar to OrganisationsEditor
# and RolesEditor. But the name UsersEditor is already used by the
# `eea.userseditor` package, which lets users edit their own profile info.
class UsersAdmin(SimpleItem, PropertyManager):
    meta_type = 'Eionet Users Admin'
    security = ClassSecurityInfo()
    icon = '++resource++eea.ldapadmin-www/users_admin.gif'

    manage_options = (
        {'label':'Configure', 'action':'manage_edit'},
        {'label':'View', 'action':''},
    ) + PropertyManager.manage_options + SimpleItem.manage_options

    _properties = (
        {'id':'title', 'type': 'string', 'mode':'w', 'label': 'Title'},
    )

    _render_template = TemplateRenderer(CommonTemplateLogic)

    def __init__(self, config={}):
        super(UsersAdmin, self).__init__()
        self._config = PersistentMapping(config)

    security.declareProtected(view_management_screens, 'get_config')
    def get_config(self):
        return dict(self._config)

    security.declareProtected(view_management_screens, 'manage_edit')
    manage_edit = PageTemplateFile('zpt/users_manage_edit', globals())
    manage_edit.ldap_config_edit_macro = ldap_config.edit_macro

    security.declareProtected(view_management_screens, 'manage_edit_save')
    def manage_edit_save(self, REQUEST):
        """ save changes to configuration """
        self._config.update(ldap_config.read_form(REQUEST.form, edit=True))
        REQUEST.RESPONSE.redirect(self.absolute_url() + '/manage_edit')

    def _get_ldap_agent(self, bind=False):
        return ldap_config.ldap_agent_with_config(self._config, bind)

    security.declareProtected(view, 'can_edit_users')
    def can_edit_users(self, user):
        return bool(user.has_permission(eionet_edit_users, self))

    security.declareProtected(view, 'index_html')
    def index_html(self, REQUEST):
        """ view """
        options = {
            'can_edit': self.can_edit_users(REQUEST.AUTHENTICATED_USER),
        }
        return self._render_template('zpt/users_index.zpt', **options)

    security.declareProtected(eionet_edit_users, 'create_user')
    def create_user(self, REQUEST):
        """ view """
        options = {
            'user_form': deform.Form(user_info_schema, buttons=['submit']),
        }
        return self._render_template('zpt/users_create.zpt', **options)

InitializeClass(UsersAdmin)
