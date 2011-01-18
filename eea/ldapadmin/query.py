from AccessControl import ClassSecurityInfo
from OFS.SimpleItem import SimpleItem
from OFS.PropertyManager import PropertyManager
from Products.PageTemplates.PageTemplateFile import PageTemplateFile

import roles_editor
from ui_common import Zope3TemplateInZope2

manage_add_query_html = PageTemplateFile('zpt/query_manage_add', globals())

def manage_add_query(parent, id, title, pattern, REQUEST=None):
    """ Create a new Query object """
    obj = Query()
    obj._setId(id)
    obj.title = title
    obj.pattern = pattern
    parent._setObject(id, obj)

    if REQUEST is not None:
        url = parent.absolute_url() + '/manage_workspace'
        return REQUEST.RESPONSE.redirect(url)

class Query(SimpleItem, PropertyManager):
    meta_type = 'Eionet Roles Editor Query'
    security = ClassSecurityInfo()
    icon = 'misc_/EionetRolesEditor/query.gif'

    manage_options = PropertyManager.manage_options + (
        {'label':'View', 'action':''},
    ) + SimpleItem.manage_options

    _properties = (
        {'id':'title', 'type': 'string', 'mode':'w', 'label': 'Title'},
        {'id':'pattern', 'type': 'string', 'mode':'w', 'label': 'Pattern'},
    )

    _render_template = Zope3TemplateInZope2()

    def _get_ldap_agent(self):
        return self.aq_parent._get_ldap_agent()

    def index_html(self, REQUEST):
        """ view """
        agent = self._get_ldap_agent()
        is_authenticated = roles_editor._is_authenticated(REQUEST)
        results_html = roles_editor.filter_result_html(agent, self.pattern,
                                                       is_authenticated)
        options = {
            'pattern': self.pattern,
            'results_html': results_html,
        }
        return self._render_template('zpt/query_index.zpt', **options)
