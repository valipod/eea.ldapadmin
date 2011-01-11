from AccessControl import ClassSecurityInfo
from OFS.SimpleItem import SimpleItem
from OFS.PropertyManager import PropertyManager
from Products.PageTemplates.PageTemplateFile import PageTemplateFile

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

    index_html = PageTemplateFile('zpt/query_index', globals())
