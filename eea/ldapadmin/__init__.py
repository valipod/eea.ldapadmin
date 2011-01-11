def initialize(context):
    import editor
    constructors = (
        ('manage_add_editor_html', editor.manage_add_editor_html),
        ('manage_add_editor', editor.manage_add_editor),
    )
    context.registerClass(editor.Editor, constructors=constructors)
