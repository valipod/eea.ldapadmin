import operator
from datetime import datetime
import re
import itertools

from AccessControl import ClassSecurityInfo
from App.class_init import InitializeClass
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from OFS.SimpleItem import SimpleItem
from OFS.PropertyManager import PropertyManager
from AccessControl.Permissions import view

from ldap_agent import LdapAgent, editable_org_fields
from ui_common import load_template, SessionMessages, TemplateRenderer

eionet_edit_orgs = 'Eionet edit organisations'

manage_add_organisations_editor_html = PageTemplateFile('zpt/orgs_manage_add',
                                                        globals())
def manage_add_organisations_editor(parent, id, REQUEST=None):
    """ Adds a new Eionet Organisations Editor object """
    parent._setObject(id, OrganisationsEditor(id))
    if REQUEST is not None:
        REQUEST.RESPONSE.redirect(parent.absolute_url() + '/manage_workspace')


def get_template_macro(name):
    return load_template('zpt/orgs_macros.zpt').macros[name]

SESSION_PREFIX = 'eea.ldapadmin.orgs_editor'
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


class OrganisationsEditor(SimpleItem):
    meta_type = 'Eionet Organisations Editor'
    security = ClassSecurityInfo()
    icon = '++resource++eea.ldapadmin-orgs_editor.gif'

    manage_options = SimpleItem.manage_options[:1] + (
        {'label':'View', 'action':''},
    ) + SimpleItem.manage_options[1:]

    def __init__(self, id):
        self.id = id

    _render_template = TemplateRenderer(CommonTemplateLogic)

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
        options = {
            'sorted_organisations': orgs,
        }
        return self._render_template('zpt/orgs_index.zpt', **options)

    security.declareProtected(view, 'organisation')
    def organisation(self, REQUEST):
        """ view """
        org_id = REQUEST.form['id']
        agent = self._get_ldap_agent()
        options = {
            'organisation': agent.org_info(org_id),
        }
        return self._render_template('zpt/orgs_view.zpt', **options)

    security.declareProtected(eionet_edit_orgs, 'create_organisation_html')
    def create_organisation_html(self, REQUEST):
        """ view """
        options = {
            'form_macro': get_template_macro('org_form_fields'),
        }

        session = REQUEST.SESSION
        if SESSION_FORM_DATA in session.keys():
            options['org_info'] = session[SESSION_FORM_DATA]
            del session[SESSION_FORM_DATA]
        else:
            options['org_info'] = {}

        return self._render_template('zpt/orgs_create.zpt', **options)

    security.declareProtected(eionet_edit_orgs, 'create_organisation')
    def create_organisation(self, REQUEST):
        """ view """
        org_id = REQUEST.form['id']
        org_info = {}
        for name in editable_org_fields:
            org_info[name] = REQUEST.form.get(name)

        errors = validate_org_info(org_id, org_info)
        if errors:
            msg = "Organisation not created. Please correct the errors below."
            _set_session_message(REQUEST, 'error', msg)
            for msg in itertools.chain(*errors.values()):
                _set_session_message(REQUEST, 'error', msg)
            REQUEST.SESSION[SESSION_FORM_DATA] = dict(org_info, id=org_id)
            REQUEST.RESPONSE.redirect(self.absolute_url() +
                                      '/create_organisation_html')
            return

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

        options = {
            'form_macro': get_template_macro('org_form_fields'),
        }

        session = REQUEST.SESSION
        if SESSION_FORM_DATA in session.keys():
            options['org_info'] = session[SESSION_FORM_DATA]
            del session[SESSION_FORM_DATA]
        else:
            options['org_info'] = self._get_ldap_agent().org_info(org_id)

        return self._render_template('zpt/orgs_edit.zpt', **options)

    security.declareProtected(eionet_edit_orgs, 'edit_organisation_html')
    def edit_organisation(self, REQUEST):
        """ view """
        org_id = REQUEST.form['id']
        org_info = {}
        for name in editable_org_fields:
            org_info[name] = REQUEST.form.get(name)

        errors = validate_org_info(org_id, org_info)
        if errors:
            msg = "Organisation not modified. Please correct the errors below."
            _set_session_message(REQUEST, 'error', msg)
            for msg in itertools.chain(*errors.values()):
                _set_session_message(REQUEST, 'error', msg)
            REQUEST.SESSION[SESSION_FORM_DATA] = dict(org_info, id=org_id)
            REQUEST.RESPONSE.redirect(self.absolute_url() +
                                      '/edit_organisation_html?id=' + org_id)
            return

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
        options = {
            'org_info': self._get_ldap_agent().org_info(org_id),
        }
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
        options = {
            'organisation': agent.org_info(org_id),
            'org_members': org_members,
        }
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

        options = {
            'org_id': org_id,
            'search_query': search_query,
            'found_users': found_users,
        }
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


id_re = re.compile(r'^[a-z_]+$')
phone_re = re.compile(r'^\+[\d ]+$')
postal_code_re = re.compile(r'^[a-zA-Z]{2}[a-zA-Z0-9\- ]+$')

_phone_help = ('Telephone numbers must be in international notation (they '
               'must start with a "+" followed by digits which may be '
               'separated using spaces).')
VALIDATION_ERRORS = {
    'id': ('Invalid organisation ID. It must contain only '
                   'lowercase letters and underscores ("_").'),
    'phone': "Invalid telephone number. " + _phone_help,
    'fax': "Invalid fax number. " + _phone_help,
    'postal_code': ('Postal codes must be in international notation (they '
                    'must start with a two-letter country code followed by a '
                    'combination of digits, latin letters, dashes and '
                    'spaces).'),
}

def validate_org_info(org_id, org_info):
    errors = {}

    if id_re.match(org_id) is None:
        errors['id'] = [VALIDATION_ERRORS['id']]

    phone = org_info['phone']
    if phone and phone_re.match(phone) is None:
        errors['phone'] = [VALIDATION_ERRORS['phone']]

    fax = org_info['fax']
    if fax and phone_re.match(fax) is None:
        errors['fax'] = [VALIDATION_ERRORS['fax']]

    postal_code = org_info['postal_code']
    if postal_code and postal_code_re.match(postal_code) is None:
        errors['postal_code'] = [VALIDATION_ERRORS['postal_code']]

    return errors
