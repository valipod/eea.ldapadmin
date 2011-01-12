import unittest
from lxml.html.soupparser import fromstring
from mock import Mock
from eea.ldapadmin.orgs_editor import OrganisationsEditor

from test_ldap_agent import org_info_fixture

def parse_html(html):
    return fromstring(html)

class StubbedOrganisationsEditor(OrganisationsEditor):
    def _zope2_wrapper(self, body_html):
        return "<html>%s</html>" % body_html

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

    def test_create_org_submit(self):
        self.request.form = dict(org_info_fixture)
        self.request.form['id'] = 'bridge_club'

        self.ui.create_organisation(self.request)

        self.mock_agent.create_org.assert_called_once_with('bridge_club',
                                                           org_info_fixture)
        self.request.RESPONSE.redirect.assert_called_with('URL/')

    def test_edit_org_form(self):
        self.request.form = {'id': 'bridge_club'}
        self.mock_agent.org_info.return_value = dict(org_info_fixture,
                                                     id='bridge_club')

        page = parse_html(self.ui.edit_organisation_html(self.request))

        self.mock_agent.org_info.assert_called_once_with('bridge_club')

        form = page.xpath('//form')[0]
        self.assertEqual(form.attrib['action'], 'URL/edit_organisation')
        self.assertEqual(form.xpath('//input[@name="id"]')[0].attrib['value'],
                         'bridge_club')
        for name, value in org_info_fixture.iteritems():
            if name == 'address':
                xp = '//textarea[@name="%s:utf8:ustring"]' % name
                frm_value = form.xpath(xp)[0].text
            else:
                xp = '//input[@name="%s:utf8:ustring"]' % name
                frm_value = form.xpath(xp)[0].attrib['value']
            self.assertEqual(frm_value, value)

    def test_edit_org_submit(self):
        self.request.form = dict(org_info_fixture, id='bridge_club')

        self.ui.edit_organisation(self.request)

        self.mock_agent.set_org_info.assert_called_once_with(
            'bridge_club', org_info_fixture)
        self.request.RESPONSE.redirect.assert_called_with(
            'URL/organisation?id=bridge_club')

    def test_list_organisations(self):
        self.mock_agent.all_organisations.return_value = {
            'bridge_club': "Bridge club",
            'poker_club': u"P\xf8ker club",
        }

        page = parse_html(self.ui.index_html(self.request))

        orgs_ul = page.xpath('//ul[@class="organisations"]')[0]
        org_0 = orgs_ul.xpath('li')[0]
        org_1 = orgs_ul.xpath('li')[1]
        self.assertEqual(org_0.xpath('a')[0].text.strip(), "Bridge club")
        self.assertEqual(org_1.xpath('a')[0].text.strip(), u"P\xf8ker club")
        self.assertEqual(org_0.xpath('a')[0].attrib['href'],
                         'URL/organisation?id=bridge_club')

    def test_org_info_page(self):
        self.request.form = {'id': 'bridge_club'}
        self.mock_agent.org_info.return_value = dict(org_info_fixture,
                                                     id='bridge_club')

        page = parse_html(self.ui.organisation(self.request))

        org_h1 = page.xpath('//h1')[0]
        self.assertEqual(org_h1.text.strip(), "Ye olde bridge club")

        org_table = page.xpath('//table')[0]
        def html_value(label):
            xp = '//tr[td[text()="%s"]]/td[2]' % label
            return org_table.xpath(xp)[0].text
        self.assertEqual(html_value('Name:'), org_info_fixture['name'])
        self.assertEqual(html_value('URL:'), org_info_fixture['url'])
        self.assertEqual(html_value('Phone:'), org_info_fixture['phone'])
        self.assertEqual(html_value('Fax:'), org_info_fixture['fax'])
        self.assertEqual(html_value('Street:'), org_info_fixture['street'])
        self.assertEqual(html_value('PO box:'), org_info_fixture['po_box'])
        self.assertEqual(html_value('Postal code:'),
                         org_info_fixture['postal_code'])
        self.assertEqual(html_value('Locality:'), org_info_fixture['locality'])
        self.assertEqual(html_value('Country:'), org_info_fixture['country'])
        self.assertEqual(html_value('Full address:'),
                         org_info_fixture['address'])

    def test_remove_org_page(self):
        import re
        self.request.form = {'id': 'bridge_club'}
        self.mock_agent.org_info.return_value = dict(org_info_fixture,
                                                     id='bridge_club')

        page = parse_html(self.ui.remove_organisation_html(self.request))

        txt = page.xpath('//p[@class="confirm-delete"]')[0].text_content()
        self.assertEqual(re.sub(r'\s+', ' ', txt.strip()),
                         ("Are you sure you want to remove the organisation "
                          "Ye olde bridge club (bridge_club)?"))
        id_input = page.xpath('//form//input[@name="id"]')[0]
        self.assertEqual(id_input.attrib['value'], 'bridge_club')

    def test_remove_org_submit(self):
        self.request.form = {'id': 'bridge_club'}

        self.ui.remove_organisation(self.request)

        self.mock_agent.delete_org.assert_called_once_with('bridge_club')
        self.request.RESPONSE.redirect.assert_called_with('URL/')
