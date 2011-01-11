def initialize(context):
    import roles_editor, orgs_editor
    context.registerClass(roles_editor.RolesEditor, constructors=(
        ('manage_add_editor_html', roles_editor.manage_add_editor_html),
        ('manage_add_editor', roles_editor.manage_add_editor),
    ))
    context.registerClass(orgs_editor.OrganisationsEditor, constructors=(
        ('manage_add_organisations_editor_html',
         orgs_editor.manage_add_organisations_editor_html),
        ('manage_add_organisations_editor',
         orgs_editor.manage_add_organisations_editor),
    ))
