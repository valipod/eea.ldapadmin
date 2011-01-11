from AccessControl import ClassSecurityInfo
from Globals import InitializeClass
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from OFS.SimpleItem import SimpleItem
from OFS.PropertyManager import PropertyManager
from AccessControl.Permissions import view

from ldap_agent import LdapAgent


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


class OrganisationsEditor(SimpleItem):
    meta_type = 'Eionet Organisations Editor'
    icon = 'misc_/EionetRolesEditor/orgs_editor.gif'
    manage_options = SimpleItem.manage_options[:1] + (
        {'label':'View', 'action':''},
    ) + SimpleItem.manage_options[1:]
    security = ClassSecurityInfo()

    def __init__(self, id):
        self.id = id

    _zope2_wrapper = PageTemplateFile('zpt/zope2_wrapper.zpt', globals())
    def _render_template(self, name, **options):
        tmpl = load_template(name)
        return self._zope2_wrapper(body_html=tmpl(**options))

    def _get_ldap_agent(self):
        raise NotImplementedError

    security.declareProtected(view, 'create_organisation_html')
    def create_organisation_html(self, REQUEST):
        """ view """
        options = {'base_url': self.absolute_url()}
        return self._render_template('zpt/orgs_create.zpt', **options)

InitializeClass(OrganisationsEditor)
