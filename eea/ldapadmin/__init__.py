def initialize(context):
    import roles_editor, orgs_editor
    context.registerClass(roles_editor.RolesEditor, constructors=(
        ('manage_add_roles_editor_html',
         roles_editor.manage_add_roles_editor_html),
        ('manage_add_roles_editor', roles_editor.manage_add_roles_editor),
    ))
    context.registerClass(orgs_editor.OrganisationsEditor, constructors=(
        ('manage_add_orgs_editor_html',
         orgs_editor.manage_add_orgs_editor_html),
        ('manage_add_orgs_editor', orgs_editor.manage_add_orgs_editor),
    ))
