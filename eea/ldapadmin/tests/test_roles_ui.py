import unittest
from copy import deepcopy
from mock import Mock
from eea.ldapadmin.roles_editor import RolesEditor, CommonTemplateLogic
from eea.ldapadmin.ui_common import TemplateRenderer
from eea.ldapadmin import ldap_agent

def plaintext(element):
    import re
    return re.sub(r'\s\s+', ' ', element.text_content()).strip()

def parse_html(html):
    from lxml.html.soupparser import fromstring
    return fromstring(html)

def stubbed_renderer():
    renderer = TemplateRenderer(CommonTemplateLogic)
    renderer.wrap = lambda html: "<html>%s</html>" % html
    return renderer

class StubbedRolesEditor(RolesEditor):
    def __init__(self):
        super(StubbedRolesEditor, self).__init__()
        self._render_template = stubbed_renderer()

    def absolute_url(self):
        return "URL"

def mock_request():
    request = Mock()
    request.SESSION = {}
    return request

user_map_fixture = {
    'jsmith': {
        'id': "jsmith",
        'name': "Joe Smith",
        'email': u"jsmith@example.com",
        'phone': u"555 1234",
        'fax': u"555 6789",
        'organisation': "My company",
    },
    'anne': {
        'id': "anne",
        'name': "Anne Tester",
        'email': u"anne@example.com",
        'phone': u"555 32879",
        'fax': u"",
        'organisation': "Some Agency",
    },
}

org_map_fixture = {
    'bridge_club': {
        'id': 'bridge_club',
        'name': u"Ye olde bridge club",
        'url': u"http://bridge-club.example.com/",
    },
    'poker_club': {
        'id': 'poker_club',
        'name': u"P\xf8ker club",
        'url': u"http://poker-club.example.com/",
    },
}

user_info_fixture = user_map_fixture['jsmith']

from test_ldap_agent import org_info_fixture

def session_messages(request):
    return request.SESSION.get('eea.ldapadmin.roles_editor.messages')


class BrowseTest(unittest.TestCase):
    def setUp(self):
        self.ui = StubbedRolesEditor()
        self.mock_agent = Mock()
        self.ui._get_ldap_agent = Mock(return_value=self.mock_agent)
        self.request = mock_request()
        self.request.form = {'role_id': 'places'}
        self.ui.REQUEST = self.request
        user = self.request.AUTHENTICATED_USER
        user.getRoles.return_value = ['Authenticated']
        self.mock_agent.members_in_role.return_value = {'users':[], 'orgs':[]}
        self.mock_agent.role_names_in_role.return_value = {}
        self.mock_agent.role_info.return_value = {
            'description': "Various places",
        }

    def test_browse_subroles(self):
        role_names = {'bank': "Bank for Test", 'agency': "The Agency"}
        self.mock_agent.role_names_in_role.return_value = role_names

        page = parse_html(self.ui.index_html(self.request))

        self.mock_agent.role_names_in_role.assert_called_once_with('places')
        table = page.xpath('table/tbody')[0]
        self.assertEqual(len(table.xpath('.//tr')), 2)
        tr1, tr2 = table.xpath('tr')
        self.assertEqual(plaintext(tr1.xpath('td[1]')[0]), "agency")
        self.assertEqual(plaintext(tr1.xpath('td[2]')[0]), "The Agency")
        self.assertEqual(plaintext(tr2.xpath('td[1]')[0]), "bank")
        self.assertEqual(plaintext(tr2.xpath('td[2]')[0]), "Bank for Test")

    def test_browse_role_info(self):
        page = parse_html(self.ui.index_html(self.request))

        self.assertEqual(page.xpath('//h1')[0].text, "Various places")
        self.mock_agent.role_info.assert_called_once_with('places')

    def test_user_info(self):
        self.mock_agent.members_in_role.return_value = {
            'users': ['jsmith'], 'orgs': [],
        }
        self.mock_agent.user_info.return_value = dict(user_info_fixture)

        page = parse_html(self.ui.index_html(self.request))

        self.mock_agent.members_in_role.assert_called_once_with('places')
        self.mock_agent.user_info.assert_called_once_with('jsmith')

        cells = page.xpath('table[@class="account-datatable"]/tbody/tr/td')
        self.assertEqual(plaintext(cells[0]), user_info_fixture['name'])
        self.assertEqual(plaintext(cells[1]), 'jsmith')
        self.assertEqual(plaintext(cells[2]), user_info_fixture['email'])
        self.assertEqual(plaintext(cells[4]), user_info_fixture['organisation'])

    def test_org_info(self):
        self.mock_agent.members_in_role.return_value = {
            'users': [], 'orgs': ['bridge-club'],
        }
        self.mock_agent.org_info.return_value = dict(org_info_fixture,
                                                     id='bridge-club')

        page = parse_html(self.ui.index_html(self.request))

        self.mock_agent.members_in_role.assert_called_once_with('places')
        self.mock_agent.org_info.assert_called_once_with('bridge-club')

        cells = page.xpath('table[@class="account-datatable"]/tbody/tr/td')
        self.assertEqual(plaintext(cells[0]), org_info_fixture['name'])
        self.assertEqual(plaintext(cells[1]), org_info_fixture['url'])

    def test_missing_role(self):
        exc = ldap_agent.RoleNotFound("no-such-role")
        self.mock_agent.role_info.side_effect = exc
        self.request.form = {'role_id': 'no-such-role'}

        page = parse_html(self.ui.index_html(self.request))

        self.assertEqual(plaintext(page.xpath('//p[@class="message"]')[0]),
                         "Role no-such-role does not exist.")
        self.request.RESPONSE.setStatus.assert_called_once_with(404)


class CreateDeleteRolesTest(unittest.TestCase):
    def setUp(self):
        self.ui = StubbedRolesEditor()
        self.mock_agent = Mock()
        self.ui._get_ldap_agent = Mock(return_value=self.mock_agent)
        self.request = mock_request()
        user = self.request.AUTHENTICATED_USER
        user.getRoles.return_value = ['Authenticated']
        self.ui.REQUEST = self.request
        def agent_role_id(role_dn):
            assert role_dn.startswith('test-dn:')
            return role_dn[len('test-dn:'):]
        self.mock_agent._role_id = agent_role_id

    def test_link_from_browse(self):
        self.mock_agent.members_in_role.return_value = {'users':[], 'orgs':[]}
        self.mock_agent.role_names_in_role.return_value = {}
        self.mock_agent.role_info.return_value = {
            'description': "Various places",
        }
        self.request.form = {'role_id': 'places'}

        page = parse_html(self.ui.index_html(self.request))

        create_url = "URL/create_role_html?parent_role_id=places"
        create_links = page.xpath('//a[@href="%s"]' % create_url)
        self.assertEqual(len(create_links), 1)
        self.assertEqual(plaintext(create_links[0]), "Create sub-role")

        delete_url = "URL/delete_role_html?role_id=places"
        delete_links = page.xpath('//a[@href="%s"]' % delete_url)
        self.assertEqual(len(delete_links), 1)
        self.assertEqual(plaintext(delete_links[0]), "Delete role places")

    def test_create_role_html(self):
        self.request.form = {'parent_role_id': 'places'}

        page = parse_html(self.ui.create_role_html(self.request))

        self.assertEqual(plaintext(page.xpath('//h1')[0]),
                         "Create role under places")
        self.assertEqual(page.xpath('//form')[0].attrib['action'],
                         "URL/create_role")
        input_parent = page.xpath('//form//input[@name="parent_role_id"]')[0]
        self.assertEqual(input_parent.attrib['value'], 'places')
        input_desc_xpath = '//form//input[@name="description:utf8:ustring"]'
        self.assertEqual(len(page.xpath(input_desc_xpath)), 1)

    def test_create_role_submit(self):
        self.request.form = {'parent_role_id': 'places', 'slug': 'shiny',
                             'description': "Shiny new role"}

        self.ui.create_role(self.request)

        self.mock_agent.create_role.assert_called_once_with(
            'places-shiny', "Shiny new role")
        self.request.RESPONSE.redirect.assert_called_with(
            'URL/?role_id=places-shiny')

        msg = 'Created role places-shiny "Shiny new role"'
        self.assertEqual(session_messages(self.request), {'info': [msg]})

    def test_create_role_submit_unicode(self):
        self.request.form = {'parent_role_id': 'places', 'slug': 'shiny',
                             'description': u"Shiny new r\u014dle"}
        self.ui.create_role(self.request)
        self.mock_agent.create_role.assert_called_once_with(
            'places-shiny', u"Shiny new r\u014dle")

    def test_create_role_submit_invalid(self):
        self.request.form = {'parent_role_id': 'places', 'slug': 'SHINY',
                             'description': "Shiny new role"}
        self.ui.create_role(self.request)
        self.assertEqual(self.mock_agent.create_role.call_count, 0)

        self.request.RESPONSE.redirect.assert_called_with(
            'URL/create_role_html?parent_role_id=places')

        msg = ("Invalid role name, it must contain only lowercase "
               "latin letters.")
        self.assertEqual(session_messages(self.request), {'error': [msg]})

        self.request.form = {'parent_role_id': 'places'}
        #print self.ui.create_role_html(self.request)
        page = parse_html(self.ui.create_role_html(self.request))

        role_id_xp = '//form//input[@name="slug:utf8:ustring"]'
        role_desc_xp = '//form//input[@name="description:utf8:ustring"]'
        self.assertEqual(page.xpath(role_id_xp)[0].attrib['value'], 'SHINY')
        self.assertEqual(page.xpath(role_desc_xp)[0].attrib['value'],
                         "Shiny new role")

    def test_delete_role_html(self):
        self.request.form = {'role_id': 'places-bank'}
        self.mock_agent._sub_roles.return_value = [
            'test-dn:places-bank',
            'test-dn:places-bank-central',
            'test-dn:places-bank-branch',
        ]

        page = parse_html(self.ui.delete_role_html(self.request))

        self.mock_agent._sub_roles.assert_called_once_with('places-bank')
        self.assertEqual([plaintext(li) for li in
                          page.xpath('//form//tbody/tr')],
                         ['places-bank',
                          'places-bank-central',
                          'places-bank-branch'])

    def test_delete_role(self):
        self.request.form = {'role_id': 'places-bank'}

        self.ui.delete_role(self.request)

        self.mock_agent.delete_role.assert_called_once_with('places-bank')
        self.request.RESPONSE.redirect.assert_called_with(
            'URL/?role_id=places')

class AddRemoveRoleMembersTest(unittest.TestCase):
    def setUp(self):
        self.ui = StubbedRolesEditor()
        self.mock_agent = Mock()
        self.ui._get_ldap_agent = Mock(return_value=self.mock_agent)
        self.request = mock_request()
        user = self.request.AUTHENTICATED_USER
        user.getRoles.return_value = ['Authenticated']
        self.ui.REQUEST = self.request

    def test_links(self):
        self.mock_agent.members_in_role.return_value = {'users':[], 'orgs':[]}
        self.mock_agent.role_names_in_role.return_value = {}
        self.mock_agent.role_info.return_value = {
            'description': "Various places",
        }
        self.request.form = {'role_id': 'places'}

        page = parse_html(self.ui.index_html(self.request))

        add_member_url = "URL/add_member_html?role_id=places"
        add_member_links = page.xpath('//a[@href="%s"]' % add_member_url)
        self.assertEqual(len(add_member_links), 1)
        self.assertEqual(plaintext(add_member_links[0]), "Add members")

        rm_members_url = "URL/remove_members_html?role_id=places"
        rm_members_links = page.xpath('//a[@href="%s"]' % rm_members_url)
        self.assertEqual(len(rm_members_links), 1)
        self.assertEqual(plaintext(rm_members_links[0]), "Remove members")

    def test_add_user_html(self):
        self.request.form = {'role_id': 'places'}

        page = parse_html(self.ui.add_member_html(self.request))

        self.assertEqual(self.mock_agent.search_user.call_count, 0)
        self.assertEqual(plaintext(page.xpath('//h1')[0]),
                         "Add members to role places")

    def test_add_user_search_html(self):
        self.request.form = {'role_id': 'places', 'name': 'smith'}
        self.mock_agent.search_user.return_value = [user_info_fixture]
        self.mock_agent.search_org.return_value = []

        page = parse_html(self.ui.add_member_html(self.request))

        self.mock_agent.search_user.assert_called_once_with('smith')
        name = plaintext(page.xpath('//tbody/tr/td')[0])
        self.assertEqual(name, "Joe Smith jsmith@example.com")
        form = page.xpath('//form[@name="add-user"]')[0]
        self.assertEqual(form.attrib['action'], 'URL/add_user')

    def test_add_user_search_html_no_results(self):
        self.request.form = {'role_id': 'places', 'name': 'smith'}
        self.mock_agent.search_user.return_value = []
        self.mock_agent.search_org.return_value = []

        page = parse_html(self.ui.add_member_html(self.request))

        self.assertEqual(plaintext(page.cssselect('p.search-message')[0]),
                         "No matching users or organisations for smith.")

    def test_add_user_submit(self):
        self.request.form = {'role_id': 'places-bank', 'user_id': 'jsmith'}
        self.mock_agent.add_to_role.return_value = ['places', 'places-bank']

        self.ui.add_user(self.request)

        self.mock_agent.add_to_role.assert_called_once_with(
            'places-bank', 'user', 'jsmith')
        self.request.RESPONSE.redirect.assert_called_with(
            'URL/?role_id=places-bank')
        msg = "User 'jsmith' added to roles 'places', 'places-bank'."
        self.assertEqual(session_messages(self.request), {'info': [msg]})

    def test_remove_users_html(self):
        self.mock_agent.members_in_role.return_value = {'users':['jsmith'],
                                                        'orgs':[]}
        self.mock_agent.role_names_in_role.return_value = {}
        self.mock_agent.role_info.return_value = {
            'description': "Various places",
        }
        self.mock_agent.user_info.return_value = dict(user_info_fixture,
                                                      id='jsmith')
        self.request.form = {'role_id': 'places'}

        page = parse_html(self.ui.remove_members_html(self.request))

        remove_form = page.xpath('//form[@name="remove-users"]')[0]
        self.assertEqual(remove_form.attrib['action'], 'URL/remove_members')
        user_tr = remove_form.xpath('.//tbody/tr')[0]
        user_checkbox = user_tr.xpath('.//input[@name="user_id_list:list"]')[0]
        self.assertEqual(user_checkbox.attrib['value'], 'jsmith')

    def test_remove_users_submit(self):
        self.request.form = {'role_id': 'places', 'user_id_list': ['jsmith']}

        self.ui.remove_members(self.request)

        self.request.RESPONSE.redirect.assert_called_with(
            'URL/?role_id=places')
        msg = "Users ['jsmith'] removed from role 'places'"
        self.assertEqual(session_messages(self.request), {'info': [msg]})

    def test_remove_users_submit_nothing(self):
        self.request.form = {'role_id': 'places'}

        self.ui.remove_members(self.request)

        self.request.RESPONSE.redirect.assert_called_with(
            'URL/?role_id=places')
        self.assertEqual(session_messages(self.request), None)

    def test_add_org_html(self):
        self.request.form = {'role_id': 'places'}

        page = parse_html(self.ui.add_member_html(self.request))

        self.assertEqual(self.mock_agent.search_org.call_count, 0)
        self.assertEqual(plaintext(page.xpath('//h1')[0]),
                         "Add members to role places")

    def test_add_org_search_html(self):
        self.request.form = {'role_id': 'places', 'name': 'club'}
        self.mock_agent.search_user.return_value = []
        self.mock_agent.search_org.return_value = [
            dict(org_info_fixture, id='club')]

        page = parse_html(self.ui.add_member_html(self.request))

        self.mock_agent.search_org.assert_called_once_with('club')
        name = plaintext(page.xpath('//tbody/tr/td')[0])
        self.assertEqual(name, "Ye olde bridge club")
        form = page.xpath('//form[@name="add-org"]')[0]
        self.assertEqual(form.attrib['action'], 'URL/add_org')

    def test_add_org_search_html_no_results(self):
        self.request.form = {'role_id': 'places', 'name': 'club'}
        self.mock_agent.search_user.return_value = []
        self.mock_agent.search_org.return_value = []

        page = parse_html(self.ui.add_member_html(self.request))

        self.assertEqual(plaintext(page.cssselect('p.search-message')[0]),
                         "No matching users or organisations for club.")

    def test_add_org_submit(self):
        self.request.form = {'role_id': 'places-bank', 'org_id': 'bridge-club'}
        self.mock_agent.add_to_role.return_value = ['places', 'places-bank']

        self.ui.add_org(self.request)

        self.mock_agent.add_to_role.assert_called_once_with(
            'places-bank', 'org', 'bridge-club')
        self.request.RESPONSE.redirect.assert_called_with(
            'URL/?role_id=places-bank')
        msg = ("Organisation 'bridge-club' added to roles "
               "'places', 'places-bank'.")
        self.assertEqual(session_messages(self.request), {'info': [msg]})

    def test_remove_orgs_html(self):
        self.mock_agent.members_in_role.return_value = {'users':[],
                                                        'orgs':['bridge-club']}
        self.mock_agent.role_names_in_role.return_value = {}
        self.mock_agent.role_info.return_value = {
            'description': "Various places",
        }
        self.mock_agent.org_info.return_value = dict(org_info_fixture,
                                                     id='bridge-club')
        self.request.form = {'role_id': 'places'}

        page = parse_html(self.ui.remove_members_html(self.request))

        remove_form = page.xpath('//form[@name="remove-orgs"]')[0]
        self.assertEqual(remove_form.attrib['action'], 'URL/remove_members')
        org_li = remove_form.xpath('.//table/tbody/tr')[0]
        org_checkbox = org_li.xpath('.//input[@name="org_id_list:list"]')[0]
        self.assertEqual(org_checkbox.attrib['value'], 'bridge-club')

    def test_remove_orgs_submit(self):
        self.request.form = {'role_id': 'places',
                             'org_id_list': ['bridge-club']}

        self.ui.remove_members(self.request)

        self.request.RESPONSE.redirect.assert_called_with(
            'URL/?role_id=places')
        msg = "Organisations ['bridge-club'] removed from role 'places'"
        self.assertEqual(session_messages(self.request), {'info': [msg]})

    def test_remove_orgs_submit_nothing(self):
        self.request.form = {'role_id': 'places'}

        self.ui.remove_members(self.request)

        self.request.RESPONSE.redirect.assert_called_with(
            'URL/?role_id=places')
        self.assertEqual(session_messages(self.request), None)


class UserSearchTest(unittest.TestCase):
    def setUp(self):
        self.ui = StubbedRolesEditor()
        self.mock_agent = Mock()
        self.mock_agent.is_subrole = lambda r1, r2: r1.startswith(r2)
        self.ui._get_ldap_agent = Mock(return_value=self.mock_agent)
        self.request = mock_request()
        user = self.request.AUTHENTICATED_USER
        user.getRoles.return_value = ['Authenticated']
        self.ui.REQUEST = self.request

    def test_plain(self):
        self.request.form = {}
        page = parse_html(self.ui.search_users(self.request))

        form = page.xpath('//form[@name="search-users"]')[0]
        self.assertEqual(len(form.xpath('.//input[@name="name"]')), 1)

    def test_results(self):
        self.request.form = {'name': 'smith'}
        self.mock_agent.search_user.return_value = [user_info_fixture]

        page = parse_html(self.ui.search_users(self.request))

        self.mock_agent.search_user.assert_called_once_with('smith')
        name = plaintext(page.xpath('//ul/li/span[@class="user-name"]')[0])
        self.assertEqual(name, "Joe Smith")

    def test_no_result(self):
        self.request.form = {'name': 'smith'}
        self.mock_agent.search_user.return_value = []

        page = parse_html(self.ui.search_users(self.request))

        self.assertEqual(plaintext(page.xpath('//p[@class="no-results"]')[0]),
                         "Found no users matching smith.")

    def test_user_roles_html(self):
        self.request.form = {'user_id': 'jsmith'}
        self.mock_agent.list_member_roles.return_value = ['places-bank',
                                                          'places-bank-branch']

        page = parse_html(self.ui.search_users(self.request))

        roles_div = page.xpath('//div[@class="user-roles"]')[0]
        self.assertEqual(plaintext(roles_div.xpath('h2')[0]),
                         "User jsmith is a member of:")
        self.mock_agent.list_member_roles.assert_called_once_with(
            'user', 'jsmith')
        self.assertEqual([plaintext(li) for li in roles_div.xpath('ul/li')],
                         ['places-bank', 'places-bank-branch'])

    def test_user_remove_from_role_html(self):
        self.request.form = {'role_id': 'places', 'user_id': 'jsmith'}
        self.mock_agent.list_member_roles.return_value = [
            'places', 'places-bank', 'places-bank-central']

        page = parse_html(self.ui.remove_user_from_role_html(self.request))

        self.assertEqual(plaintext(page.xpath('//h1')[0]), "Revoke membership")
        self.assertEqual(page.xpath('//form')[0].attrib['action'],
                         'URL/remove_user_from_role')
        self.assertEqual(plaintext(page.xpath('//form//p')[0]),
                         "Remove jsmith from the following roles:")
        self.assertEqual([plaintext(li) for li in page.xpath('//form/ul/li')],
                         ['places', 'places-bank', 'places-bank-central'])

    def test_user_remove_from_role_submit(self):
        self.request.form = {'role_id': 'places', 'user_id': 'jsmith'}
        role_ids = ['places-bank', 'places-bank-central']
        self.mock_agent.remove_from_role.return_value = role_ids

        self.ui.remove_user_from_role(self.request)

        self.mock_agent.remove_from_role.assert_called_once_with(
            'places', 'user', 'jsmith')
        self.request.RESPONSE.redirect.assert_called_with(
             'URL/search_users?user_id=jsmith')
        msg = ("User 'jsmith' removed from roles "
               "'places-bank', 'places-bank-central'.")
        self.assertEqual(session_messages(self.request), {'info': [msg]})

class FilterTest(unittest.TestCase):
    def setUp(self):
        self.ui = StubbedRolesEditor()
        self.mock_agent = Mock()
        self.ui._get_ldap_agent = Mock(return_value=self.mock_agent)
        self.request = mock_request()
        user = self.request.AUTHENTICATED_USER
        user.getRoles.return_value = ['Authenticated']
        self.ui.REQUEST = self.request

        role_membership = {
            'places-bank': {'users': sorted(user_map_fixture.keys()),
                            'orgs': sorted(org_map_fixture.keys())},
            'places-shiny': {'users': [], 'orgs': []},
        }
        self.mock_agent.filter_roles.return_value = role_membership.keys()
        self.mock_agent.members_in_role.side_effect = role_membership.get
        self.mock_agent.user_info.side_effect = deepcopy(user_map_fixture).get
        self.mock_agent.org_info.side_effect = deepcopy(org_map_fixture).get

    def check_query_results(self, page):
        self.assertEqual([plaintext(tt) for tt in page.xpath('//h3')],
                         ["Users in places-bank",
                          "Organisations in places-bank"])
        # TODO we should also list places-shiny somehow

        user_names = [plaintext(s) for s in
                      page.xpath('//table[1]/tbody/tr/td[1]')]
        expected_user_names = [user_map_fixture[user_id]['name']
                               for user_id in sorted(user_map_fixture)]
        self.assertEqual(user_names, expected_user_names)

        org_names = [s.text for s in page.xpath('//span[@class="org-name"]')]
        expected_org_names = [org_map_fixture[org_id]['name']
                              for org_id in sorted(org_map_fixture)]
        self.assertEqual(org_names, expected_org_names)

    def test_filter_html(self):
        self.request.form = {'pattern': 'places-*'}

        page = parse_html(self.ui.filter(self.request))

        pattern_input = page.xpath('//form/input[@type="search"]')[0]
        self.assertEqual(pattern_input.attrib['value'], 'places-*')
        self.check_query_results(page)

    def test_no_results(self):
        self.request.form = {'pattern': 'places-*'}
        self.mock_agent.filter_roles.return_value = []

        page = parse_html(self.ui.filter(self.request))

        self.assertEqual(plaintext(page.cssselect('p.search-message')[0]),
                         "No roles found matching places-*.")
