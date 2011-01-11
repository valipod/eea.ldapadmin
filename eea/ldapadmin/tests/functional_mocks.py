import logging
log = logging.getLogger('eea.ldapadmin.tests.functional_mocks')
log.setLevel(logging.DEBUG)

from zope.interface import Interface

class IMockLdapDirective(Interface):
    """ ZCML Directive that enables LDAP mocking for testing purposes """

class IMockMailDirective(Interface):
    """ ZCML Directive that enables e-mail mocking for testing purposes """

def mock_ldap(_context, **kwargs):
    import simplejson as json
    from eea.ldapadmin import ldap_agent
    import mock_ldap
    from OFS.Folder import Folder

    ldap_agent.ldap = mock_ldap

    def mock_ldap_load(self, data_json):
        """ load JSON data into LDAP mock """
        mock_ldap.data = json.loads(data_json)
        log.info("LDAP mock data loaded")
        return "LDAP mock data loaded"

    def mock_ldap_dump(self, RESPONSE=None):
        """ dump LDAP mock data as JSON """
        if RESPONSE is not None:
            RESPONSE.setHeader('Content-Type', 'application/json')
        return json.dumps(mock_ldap.data)

    Folder.mock_ldap_load = mock_ldap_load
    Folder.mock_ldap_dump = mock_ldap_dump

    log.info("LDAP mocking ready")

divert_mail = None

def mock_mail(_context, **kwargs):
    import simplejson as json
    from OFS.Folder import Folder

    saved_mails = []
    global divert_mail
    divert_mail = saved_mails.append

    def mock_mail_dump(self, RESPONSE=None):
        """ dump saved mails """
        if RESPONSE is not None:
            RESPONSE.setHeader('Content-Type', 'application/json')
        return json.dumps(saved_mails)

    def mock_mail_clear(self):
        """ clear saved mails """
        saved_mails[:] = []
        log.info("Mail mock cleared messages")
        return "ok"

    Folder.mock_mail_dump = mock_mail_dump
    Folder.mock_mail_clear = mock_mail_clear

    log.info("Mail mocking ready")
