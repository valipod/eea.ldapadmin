import operator
from datetime import datetime

from AccessControl import ClassSecurityInfo
from App.class_init import InitializeClass
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from OFS.SimpleItem import SimpleItem
from OFS.PropertyManager import PropertyManager
from AccessControl.Permissions import view
from persistent.mapping import PersistentMapping

from ldap_agent import LdapAgent, editable_org_fields

eionet_edit_orgs = 'Eionet edit organisations'

manage_add_organisations_editor_html = PageTemplateFile('zpt/orgs_manage_add',
                                                        globals())
def manage_add_organisations_editor(parent, id, REQUEST=None):
    """ Adds a new Eionet Organisations Editor object """
    parent._setObject(id, OrganisationsEditor(id))
    if REQUEST is not None:
        REQUEST.RESPONSE.redirect(parent.absolute_url() + '/manage_workspace')


def load_template(name, _memo={}):
    if name not in _memo:
        from zope.pagetemplate.pagetemplatefile import PageTemplateFile
        _memo[name] = PageTemplateFile(name, globals())
    return _memo[name]

def get_template_macro(name):
    return load_template('zpt/orgs_macros.zpt').macros[name]

SESSION_MESSAGES = 'eea.ldapadmin.orgs_editor.messages'

def _get_session_messages(request):
    session = request.SESSION
    if SESSION_MESSAGES in session.keys():
        msgs = dict(session[SESSION_MESSAGES])
        del session[SESSION_MESSAGES]
    else:
        msgs = {}
    return msgs

def _set_session_message(request, msg_type, msg):
    session = request.SESSION
    if SESSION_MESSAGES not in session.keys():
        session[SESSION_MESSAGES] = PersistentMapping()
    # TODO: allow for more than one message of each type
    session[SESSION_MESSAGES][msg_type] = msg


class OrganisationsEditor(SimpleItem):
    meta_type = 'Eionet Organisations Editor'
    security = ClassSecurityInfo()
    icon = '++resource++eea.ldapadmin-orgs_editor.gif'

    manage_options = SimpleItem.manage_options[:1] + (
        {'label':'View', 'action':''},
    ) + SimpleItem.manage_options[1:]

    def __init__(self, id):
        self.id = id

    _zope2_wrapper = PageTemplateFile('zpt/zope2_wrapper.zpt', globals())
    def _render_template(self, name, **options):
        tmpl = load_template(name)
        return self._zope2_wrapper(body_html=tmpl(**options))

    def _get_ldap_agent(self):
        return LdapAgent(ldap_server='pivo.edw.ro:22389',
                         orgs_dn='ou=Organisations,o=EIONET,l=Europe')

    security.declareProtected(view, 'index_html')
    def index_html(self, REQUEST):
        """ view """
        agent = self._get_ldap_agent()
        orgs_by_id = agent.all_organisations()
        orgs = [{'name': name, 'id': org_id}
                for org_id, name in orgs_by_id.iteritems()]
        orgs.sort(key=operator.itemgetter('name'))
        options = {'base_url': self.absolute_url(),
                   'sorted_organisations': orgs,
                   'messages': _get_session_messages(REQUEST),
                   'messages_macro': get_template_macro('messages')}
        return self._render_template('zpt/orgs_index.zpt', **options)

    security.declareProtected(view, 'organisation')
    def organisation(self, REQUEST):
        """ view """
        org_id = REQUEST.form['id']
        agent = self._get_ldap_agent()
        options = {'base_url': self.absolute_url(),
                   'organisation': agent.org_info(org_id),
                   'messages': _get_session_messages(REQUEST),
                   'messages_macro': get_template_macro('messages')}
        return self._render_template('zpt/orgs_view.zpt', **options)

    security.declareProtected(eionet_edit_orgs, 'create_organisation_html')
    def create_organisation_html(self, REQUEST):
        """ view """
        options = {'base_url': self.absolute_url(),
                   'form_macro': get_template_macro('org_form_fields')}
        return self._render_template('zpt/orgs_create.zpt', **options)

    security.declareProtected(eionet_edit_orgs, 'create_organisation')
    def create_organisation(self, REQUEST):
        """ view """
        org_id = REQUEST.form['id']
        org_info = {}
        for name in editable_org_fields:
            org_info[name] = REQUEST.form.get(name)

        agent = self._get_ldap_agent()
        agent.perform_bind('uid=_admin,ou=Users,o=EIONET,l=Europe', '_admin')
        agent.create_org(org_id, org_info)

        msg = 'Organisation "%s" created successfully.' % org_id
        _set_session_message(REQUEST, 'info', msg)
        REQUEST.RESPONSE.redirect(self.absolute_url() +
                                  '/organisation?id=' + org_id)

    security.declareProtected(eionet_edit_orgs, 'edit_organisation_html')
    def edit_organisation_html(self, REQUEST):
        """ view """
        org_id = REQUEST.form['id']
        org_info = self._get_ldap_agent().org_info(org_id)

        options = {'base_url': self.absolute_url(),
                   'form_macro': get_template_macro('org_form_fields'),
                   'form_data': org_info}
        return self._render_template('zpt/orgs_edit.zpt', **options)

    security.declareProtected(eionet_edit_orgs, 'edit_organisation_html')
    def edit_organisation(self, REQUEST):
        """ view """
        org_id = REQUEST.form['id']
        org_info = {}
        for name in editable_org_fields:
            org_info[name] = REQUEST.form.get(name)
        # TODO validate values

        agent = self._get_ldap_agent()
        agent.perform_bind('uid=_admin,ou=Users,o=EIONET,l=Europe', '_admin')
        agent.set_org_info(org_id, org_info)

        when = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _set_session_message(REQUEST, 'info', "Organisation saved (%s)" % when)
        REQUEST.RESPONSE.redirect(self.absolute_url() +
                                  '/organisation?id=' + org_id)

    security.declareProtected(eionet_edit_orgs, 'remove_organisation_html')
    def remove_organisation_html(self, REQUEST):
        """ view """
        org_id = REQUEST.form['id']
        options = {'base_url': self.absolute_url(),
                   'org_info': self._get_ldap_agent().org_info(org_id)}
        return self._render_template('zpt/orgs_remove.zpt', **options)

    security.declareProtected(eionet_edit_orgs, 'remove_organisation')
    def remove_organisation(self, REQUEST):
        """ view """
        org_id = REQUEST.form['id']
        agent = self._get_ldap_agent()
        agent.perform_bind('uid=_admin,ou=Users,o=EIONET,l=Europe', '_admin')
        agent.delete_org(org_id)

        _set_session_message(REQUEST, 'info',
                             'Organisation "%s" has been removed.' % org_id)
        REQUEST.RESPONSE.redirect(self.absolute_url() + '/')

    security.declareProtected(eionet_edit_orgs, 'members_html')
    def members_html(self, REQUEST):
        """ view """
        org_id = REQUEST.form['id']
        agent = self._get_ldap_agent()
        org_members = [agent.user_info(user_id)
                       for user_id in agent.members_in_org(org_id)]
        org_members.sort(key=operator.itemgetter('name'))
        options = {'base_url': self.absolute_url(),
                   'organisation': agent.org_info(org_id),
                   'org_members': org_members,
                   'messages': _get_session_messages(REQUEST),
                   'messages_macro': get_template_macro('messages')}
        return self._render_template('zpt/orgs_members.zpt', **options)

    security.declareProtected(eionet_edit_orgs, 'remove_members')
    def remove_members(self, REQUEST):
        """ view """
        org_id = REQUEST.form['id']
        user_id_list = REQUEST.form['user_id']

        assert type(user_id_list) is list
        for user_id in user_id_list:
            assert type(user_id) is str

        agent = self._get_ldap_agent()
        agent.perform_bind('uid=_admin,ou=Users,o=EIONET,l=Europe', '_admin')
        agent.remove_from_org(org_id, user_id_list)

        _set_session_message(REQUEST, 'info',
                             'Removed %d members from organisation "%s".' %
                              (len(user_id_list), org_id))
        REQUEST.RESPONSE.redirect(self.absolute_url() +
                                  '/members_html?id=' + org_id)

    security.declareProtected(eionet_edit_orgs,
                              'add_members_html')
    def add_members_html(self, REQUEST):
        """ view """
        org_id = REQUEST.form['id']
        search_query = REQUEST.form.get('search_query', u"")
        assert type(search_query) is unicode

        if search_query:
            agent = self._get_ldap_agent()
            found_users = agent.search_by_name(search_query)
        else:
            found_users = []

        options = {'base_url': self.absolute_url(),
                   'org_id': org_id,
                   'search_query': search_query,
                   'found_users': found_users}
        return self._render_template('zpt/orgs_add_members.zpt', **options)

    security.declareProtected(eionet_edit_orgs, 'remove_members')
    def add_members(self, REQUEST):
        """ view """
        org_id = REQUEST.form['id']
        user_id_list = REQUEST.form['user_id']

        assert type(user_id_list) is list
        for user_id in user_id_list:
            assert type(user_id) is str

        agent = self._get_ldap_agent()
        agent.perform_bind('uid=_admin,ou=Users,o=EIONET,l=Europe', '_admin')
        agent.add_to_org(org_id, user_id_list)

        _set_session_message(REQUEST, 'info',
                             'Added %d members to organisation "%s".' %
                              (len(user_id_list), org_id))
        REQUEST.RESPONSE.redirect(self.absolute_url() +
                                  '/members_html?id=' + org_id)

InitializeClass(OrganisationsEditor)
