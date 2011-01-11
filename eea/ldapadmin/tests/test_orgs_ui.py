import unittest
import re
from lxml.html.soupparser import fromstring
from mock import Mock
from eea.ldapadmin.orgs_editor import OrganisationsEditor

def parse_html(html):
    return fromstring(re.sub(r'\s+', ' ', html))

class StubbedOrganisationsEditor(OrganisationsEditor):
    def _render_template(self, name, **options):
        from eea.ldapadmin.orgs_editor import load_template
        return "<html>%s</html>" % load_template(name)(**options)

    def absolute_url(self):
        return "URL"

def mock_request():
    request = Mock()
    request.SESSION = {}
    return request


class OrganisationsUITest(unittest.TestCase):
    def setUp(self):
        self.ui = StubbedOrganisationsEditor('organisations')
        self.mock_agent = Mock()
        self.ui._get_ldap_agent = Mock(return_value=self.mock_agent)
        self.request = mock_request()

    def test_create_org_form(self):
        page = parse_html(self.ui.create_organisation_html(self.request))

        #txt = lambda xp: page.xpath(xp)[0].text.strip()
        exists = lambda xp: len(page.xpath(xp)) > 0
        self.assertTrue(exists('//form//input[@name="id"]'))
        self.assertTrue(exists('//form//input[@name="name:utf8:ustring"]'))
        self.assertTrue(exists('//form//input[@name="url:utf8:ustring"]'))
        self.assertTrue(exists('//form//input[@name="phone:utf8:ustring"]'))
        self.assertTrue(exists('//form//input[@name="fax:utf8:ustring"]'))
        self.assertTrue(exists('//form//input[@name="street:utf8:ustring"]'))
        self.assertTrue(exists('//form//input[@name="po_box:utf8:ustring"]'))
        self.assertTrue(exists('//form//input'
                                    '[@name="postal_code:utf8:ustring"]'))
        self.assertTrue(exists('//form//input[@name="locality:utf8:ustring"]'))
        self.assertTrue(exists('//form//input[@name="country:utf8:ustring"]'))
        self.assertTrue(exists('//form//textarea'
                                    '[@name="address:utf8:ustring"]'))
