def initialize(context):
    import roles_editor
    constructors = (
        ('manage_add_editor_html', roles_editor.manage_add_editor_html),
        ('manage_add_editor', roles_editor.manage_add_editor),
    )
    context.registerClass(roles_editor.RolesEditor, constructors=constructors)
