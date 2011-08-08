def initialize(context):
    import roles_editor, orgs_editor, pwreset_tool, users_admin

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

    context.registerClass(pwreset_tool.PasswordResetTool, constructors=(
        ('manage_add_pwreset_tool_html',
         pwreset_tool.manage_add_pwreset_tool_html),
        ('manage_add_pwreset_tool', pwreset_tool.manage_add_pwreset_tool),
    ))

    context.registerClass(users_admin.UsersAdmin, constructors=(
        ('manage_add_users_admin_html',
         users_admin.manage_add_users_admin_html),
        ('manage_add_users_admin', users_admin.manage_add_users_admin),
    ))
