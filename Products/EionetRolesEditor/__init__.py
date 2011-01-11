"""
This product is simply an entry point to load the real `eea.roleseditor` code,
because it must run on Zope 2.8, where Five does not support the
`registerPackage` directive.
"""
from eea.roleseditor import editor, initialize

from App.ImageFile import ImageFile
from os import path
_www_path = path.join(path.dirname(editor.__file__), 'www')
misc_ = {
    'editor.gif': ImageFile(path.join(_www_path, 'editor.gif')),
    'query.gif': ImageFile(path.join(_www_path, 'query.gif')),
}
