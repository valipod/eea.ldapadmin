import unittest
from copy import deepcopy

import ldap
from eea.ldapadmin import ldap_agent
from mock import Mock, patch, wraps
from mock_recorder import Recorder

import fixtures

class StubbedLdapAgent(ldap_agent.LdapAgent):
    def connect(self, server):
        return Mock()

class LdapAgentTest(unittest.TestCase):
    def setUp(self):
        self.agent = StubbedLdapAgent(ldap_server='')
        self.mock_conn = self.agent.conn

    def test_user_dn_conversion(self):
        user_values = {
            'usertwo': 'uid=usertwo,ou=Users,o=EIONET,l=Europe',
            'blahsdfsd': 'uid=blahsdfsd,ou=Users,o=EIONET,l=Europe',
            'x': 'uid=x,ou=Users,o=EIONET,l=Europe',
            '12': 'uid=12,ou=Users,o=EIONET,l=Europe',
            '-': 'uid=-,ou=Users,o=EIONET,l=Europe',
        }
        for user_id, user_dn in user_values.iteritems():
            assert self.agent._user_dn(user_id) == user_dn
            assert self.agent._user_id(user_dn) == user_id
        bad_user_dns = [
            'asdf',
            'uid=a,cn=xxx,ou=Users,o=EIONET,l=Europe',
            'uid=a,ou=Groups,o=EIONET,l=Europe',
            'a,ou=Users,o=EIONET,l=Europe',
        ]
        for bad_dn in bad_user_dns:
            self.assertRaises(AssertionError, self.agent._user_id, bad_dn)

    def test_org_dn_conversion(self):
        org_values = {
            'air_agency': 'cn=air_agency,ou=Organisations,o=EIONET,l=Europe',
            'blahsdfsd': 'cn=blahsdfsd,ou=Organisations,o=EIONET,l=Europe',
            'x': 'cn=x,ou=Organisations,o=EIONET,l=Europe',
            '12': 'cn=12,ou=Organisations,o=EIONET,l=Europe',
            '-': 'cn=-,ou=Organisations,o=EIONET,l=Europe',
        }
        for org_id, org_dn in org_values.iteritems():
            assert self.agent._org_dn(org_id) == org_dn
            assert self.agent._org_id(org_dn) == org_id
        bad_org_dns = [
            'asdf',
            'cn=a,cn=xxx,ou=Organisations,o=EIONET,l=Europe',
            'cn=a,ou=Groups,o=EIONET,l=Europe',
            'a,ou=Organisations,o=EIONET,l=Europe',
        ]
        for bad_dn in bad_org_dns:
            self.assertRaises(AssertionError, self.agent._org_id, bad_dn)

    def test_role_dn_conversion(self):
        role_values = {
            'A': 'cn=A,ou=Roles,o=EIONET,l=Europe',
            'A-B': 'cn=A-B,cn=A,ou=Roles,o=EIONET,l=Europe',
            'A-C': 'cn=A-C,cn=A,ou=Roles,o=EIONET,l=Europe',
            'eionet': 'cn=eionet,ou=Roles,o=EIONET,l=Europe',
            'eionet-nfp': 'cn=eionet-nfp,cn=eionet,ou=Roles,o=EIONET,l=Europe',
            'eionet-nfp-mc': ('cn=eionet-nfp-mc,cn=eionet-nfp,cn=eionet,'
                              'ou=Roles,o=EIONET,l=Europe'),
            'eionet-nfp-mc-nl': ('cn=eionet-nfp-mc-nl,cn=eionet-nfp-mc,'
                                 'cn=eionet-nfp,cn=eionet,'
                                 'ou=Roles,o=EIONET,l=Europe'),
            None: 'ou=Roles,o=EIONET,l=Europe',
        }
        for role_id, role_dn in role_values.iteritems():
            assert self.agent._role_dn(role_id) == role_dn
            assert self.agent._role_id(role_dn) == role_id
        bad_role_dns = [
            'asdf',
            'a,ou=Users,o=EIONET,l=Europe',
            'cn=aaa-bbb,ou=Roles,o=EIONET,l=Europe',
            'cn=aaa-bbb,cn=bbb,ou=Roles,o=EIONET,l=Europe',
            'cn=cad,cn=aaa-bbb,cn=aaa,ou=Roles,o=EIONET,l=Europe',
            'cn=cad-x-aaa-bbb,cn=aaa-bbb,cn=aaa,ou=Roles,o=EIONET,l=Europe',
        ]
        for bad_dn in bad_role_dns:
            self.assertRaises(AssertionError, self.agent._role_id, bad_dn)

    def test_role_names_in_role(self):
        self.mock_conn.search_s.return_value = [
            ('cn=A,ou=Roles,o=EIONET,l=Europe', {'description': ["Role [A]"]}),
            ('cn=K,ou=Roles,o=EIONET,l=Europe', {'description': ["Role [K]"]})]
        assert self.agent.role_names_in_role(None) == {'A': "Role [A]",
                                                       'K': "Role [K]"}
        self.mock_conn.search_s.assert_called_once_with(
           'ou=Roles,o=EIONET,l=Europe', ldap.SCOPE_ONELEVEL,
           attrlist=('description',),
           filterstr='(objectClass=groupOfUniqueNames)')


        self.mock_conn.search_s = Mock()
        self.mock_conn.search_s.return_value = [
            ('cn=A-B,cn=A,ou=Roles,o=EIONET,l=Europe',
             {'description': ["Role [A B]"]}),
            ('cn=A-C,cn=A,ou=Roles,o=EIONET,l=Europe',
             {'description': ["Role [A C]"]})]
        assert self.agent.role_names_in_role('A') == {'A-B': "Role [A B]",
                                                      'A-C': "Role [A C]"}
        self.mock_conn.search_s.assert_called_once_with(
           'cn=A,ou=Roles,o=EIONET,l=Europe', ldap.SCOPE_ONELEVEL,
           attrlist=('description',),
           filterstr='(objectClass=groupOfUniqueNames)')


        self.mock_conn.search_s = Mock()
        self.mock_conn.search_s.return_value = []
        assert self.agent.role_names_in_role('A-B') == {}
        self.mock_conn.search_s.assert_called_once_with(
           'cn=A-B,cn=A,ou=Roles,o=EIONET,l=Europe', ldap.SCOPE_ONELEVEL,
           attrlist=('description',),
           filterstr='(objectClass=groupOfUniqueNames)')

    def test_members_in_role(self):
        role_dn = self.agent._role_dn
        user_dn = self.agent._user_dn
        org_dn = self.agent._org_dn

        calls_list = []
        def mock_called(dn, scope, **kwargs):
            assert kwargs == {'attrlist': ('uniqueMember',),
                              'filterstr': '(objectClass=groupOfUniqueNames)'}
            expected_dn, expected_scope, ret = calls_list.pop(0)
            assert dn == expected_dn
            assert scope == expected_scope
            return ret

        self.mock_conn.search_s.side_effect = mock_called

        # no local members
        calls_list[:] = [
            (role_dn('A'), ldap.SCOPE_BASE, [
                (role_dn('A'), {'uniqueMember': [ user_dn('userone') ]}),
             ]),
            (role_dn('A'), ldap.SCOPE_ONELEVEL, [
                (role_dn('A-B'), {'uniqueMember': [ user_dn('userone') ]}),
             ]),
        ]
        assert self.agent.members_in_role('A') == {'users': [], 'orgs': []}
        assert calls_list == [], "not all calls were made"

        # a local user
        calls_list[:] = [
            (role_dn('A'), ldap.SCOPE_BASE, [
                (role_dn('A'), {'uniqueMember': [ user_dn('userone'),
                                                  user_dn('usertwo'),
                                                  user_dn('userthree'),
                                                  org_dn('air_agency') ]}),
             ]),
            (role_dn('A'), ldap.SCOPE_ONELEVEL, [
                (role_dn('A-B'), {'uniqueMember': [ user_dn('usertwo') ]}),
                (role_dn('A-C'), {'uniqueMember': [ user_dn('userthree'),
                                                    org_dn('air_agency') ]}),
             ]),
        ]
        assert self.agent.members_in_role('A') == {'users': ['userone'],
                                                   'orgs': []}
        assert calls_list == [], "not all calls were made"

        # a local user and an organisation
        calls_list[:] = [
            (role_dn('A'), ldap.SCOPE_BASE, [
                (role_dn('A'), {'uniqueMember': [ user_dn('userone'),
                                                  user_dn('usertwo'),
                                                  user_dn('userthree'),
                                                  org_dn('air_agency') ]}),
             ]),
            (role_dn('A'), ldap.SCOPE_ONELEVEL, [
                (role_dn('A-B'), {'uniqueMember': [ user_dn('usertwo') ]}),
                (role_dn('A-C'), {'uniqueMember': [ user_dn('userthree') ]}),
             ]),
        ]
        assert self.agent.members_in_role('A') == {'users': ['userone'],
                                                   'orgs': ['air_agency']}
        assert calls_list == [], "not all calls were made"


    def test_user_info(self):
        self.mock_conn.search_s.return_value = [
            ('uid=usertwo,ou=Users,o=EIONET,l=Europe', {
                'cn': ['User Two'],
                'mail': ['user_two@example.com'],
                'telephoneNumber': ['555 1234 2'],
                'o': ['Testers Club'],
            })]

        info = self.agent.user_info('usertwo')
        self.mock_conn.search_s.assert_called_once_with(
            'uid=usertwo,ou=Users,o=EIONET,l=Europe', ldap.SCOPE_BASE,
            filterstr='(objectClass=organizationalPerson)')

        assert info['name'] == 'User Two'
        assert info['email'] == 'user_two@example.com'
        assert info['phone'] == '555 1234 2'
        assert info['organisation'] == 'Testers Club'

    def test_user_info_bad_userid(self):
        self.mock_conn.search_s.return_value = []
        self.assertRaises(AssertionError, self.agent.user_info, 'nosuchuser')

    def test_org_info(self):
        self.mock_conn.search_s.return_value = [
            ('cn=air_agency,ou=Organisations,o=EIONET,l=Europe',
             {'o': ['Agency for Air Studies'],
              'labeledURI': ['http://www.air_agency.example.com']})]
        info = self.agent.org_info('air_agency')
        self.mock_conn.search_s.assert_called_once_with(
            'cn=air_agency,ou=Organisations,o=EIONET,l=Europe',
            ldap.SCOPE_BASE)
        assert info['name'] == "Agency for Air Studies"
        assert info['url'] == "http://www.air_agency.example.com"

    def test_filter_roles(self):
        expected_results = {
            'A': ['A', 'A-B', 'A-C'],
            'A-*': ['A-B', 'A-C'],
            '*-B': ['A-B'],
            '*': ['A', 'A-B', 'A-C',
                  'K', 'K-L', 'K-L-O',
                       'K-M', 'K-M-O',
                       'K-N', 'K-N-O', 'K-N-O-P',
                              'K-N-T'],
            'K-*': ['K-L', 'K-L-O',
                    'K-M', 'K-M-O',
                    'K-N', 'K-N-O', 'K-N-O-P',
                           'K-N-T'],
            'K-N-*': ['K-N-O', 'K-N-O-P', 'K-N-T'],
            'K-*-O': ['K-L-O','K-M-O',  'K-N-O', 'K-N-O-P'],
            'asdf': [],
            '**': [],
            '': [],
        }

        role_id_list = [None, 'A', 'A-B', 'A-C', 'K', 'K-L', 'K-L-O',
                        'K-M', 'K-M-O', 'K-N', 'K-N-O', 'K-N-O-P', 'K-N-T']
        ret = [(self.agent._role_dn(role_id), {}) for role_id in role_id_list]

        for pattern, expected in expected_results.iteritems():
            self.mock_conn.search_s = Mock(return_value=deepcopy(ret))
            result = self.agent.filter_roles(pattern)
            self.mock_conn.search_s.assert_called_once_with(
                'ou=Roles,o=EIONET,l=Europe', ldap.SCOPE_SUBTREE,
                filterstr='(objectClass=groupOfUniqueNames)', attrlist=())
            assert set(expected) == set(result), \
                   "pattern %r: %r != %r" % (pattern, expected, result)

    def test_delete_role(self):
        roles_to_delete = ['K', 'K-L', 'K-L-O', 'K-M']
        self.agent._bound = True
        self.mock_conn.search_s.return_value = [ (self.agent._role_dn(r), {})
                                                 for r in roles_to_delete ]
        self.mock_conn.delete_s.return_value = (ldap.RES_DELETE, [])
        self.agent.delete_role('K')

        self.mock_conn.search_s.assert_called_once_with(
            'cn=K,ou=Roles,o=EIONET,l=Europe', ldap.SCOPE_SUBTREE,
            filterstr='(objectClass=groupOfUniqueNames)', attrlist=())

        roles_to_delete.sort()
        roles_to_delete.reverse()
        for args, kwargs in self.mock_conn.delete_s.call_args_list:
            assert kwargs == {}
            assert args == (self.agent._role_dn(roles_to_delete.pop(0)),)
        assert roles_to_delete == []

        # TODO: assert error when deleting non-existent role
        # TODO: test deleting top-level role

class TestCreateRole(unittest.TestCase):
    def setUp(self):
        self.agent = StubbedLdapAgent(ldap_server='')
        self.mock_conn = self.agent.conn
        self.agent._bound = True

    def test_create(self):
        self.mock_conn.add_s.return_value=(ldap.RES_ADD, [])
        self.agent.create_role('A-B-X', "My new test role")
        self.mock_conn.add_s.assert_called_once_with(
            'cn=A-B-X,cn=A-B,cn=A,ou=Roles,o=EIONET,l=Europe',
            [('objectClass', ['top', 'groupOfUniqueNames']),
             ('ou', ['X']),
             ('uniqueMember', ['']),
             ('description', ['My new test role'])])

    def test_existing_role(self):
        self.mock_conn.add_s.side_effect = ldap.NO_SUCH_OBJECT
        self.assertRaises(ValueError, self.agent.create_role, 'A-C', "blah")

    def test_missing_parent(self):
        self.mock_conn.add_s.side_effect = ldap.ALREADY_EXISTS
        self.assertRaises(ValueError, self.agent.create_role, 'A-X-Y', "blah")

    def test_empty_description(self):
        self.mock_conn.add_s.return_value = (ldap.RES_ADD, [])
        self.agent.create_role('A-B-Z', "")
        self.mock_conn.add_s.assert_called_once_with(
            'cn=A-B-Z,cn=A-B,cn=A,ou=Roles,o=EIONET,l=Europe',
            [('objectClass',
             ['top', 'groupOfUniqueNames']),
             ('ou', ['Z']),
             ('uniqueMember', [''])])

    def test_create_top_role(self):
        self.mock_conn.add_s.return_value = (ldap.RES_ADD, [])
        self.agent.create_role('T', "top role")
        self.mock_conn.add_s.assert_called_once_with(
            'cn=T,ou=Roles,o=EIONET,l=Europe',
            [('objectClass', ['top', 'groupOfUniqueNames']),
             ('ou', ['T']),
             ('uniqueMember', ['']),
             ('description', ['top role']),])

class TestAddToRole(unittest.TestCase):
    def setUp(self):
        self.agent = StubbedLdapAgent(ldap_server='')
        self.mock_conn = self.agent.conn
        self.agent._bound = True

    def test_missing_user(self):
        user_dn = self.agent._user_dn
        role_dn = self.agent._role_dn

        self.mock_conn.search_s.return_value = []

        self.assertRaises(ValueError, self.agent._add_member_dn_to_role_dn,
                          role_dn('K-N-O'), user_dn('x'))

        self.mock_conn.search_s.assert_called_once_with(
                user_dn('x'), ldap.SCOPE_BASE, attrlist=())

    def test_missing_role(self):
        user_dn = self.agent._user_dn
        role_dn = self.agent._role_dn

        recorder = self.mock_conn.search_s.side_effect = Recorder()
        recorder.expect(user_dn('userone'), ldap.SCOPE_BASE, attrlist=(),
                        return_value=[(user_dn('userone'), {})])
        recorder.expect(role_dn('K-N-X'), ldap.SCOPE_BASE, attrlist=(),
                        return_value=[])

        self.assertRaises(ValueError, self.agent._add_member_dn_to_role_dn,
                          role_dn('K-N-X'), user_dn('userone'))

        recorder.assert_end()

    def test_add(self):
        user_dn = self.agent._user_dn
        role_dn = self.agent._role_dn

        search_recorder = self.mock_conn.search_s.side_effect = Recorder()
        search_recorder.expect(user_dn('userone'), ldap.SCOPE_BASE,
                               attrlist=(),
                               return_value=[(user_dn('userone'), {})])
        search_recorder.expect(role_dn('K-N-O'), ldap.SCOPE_BASE, attrlist=(),
                               return_value=[(role_dn('K-N-O'), {})])

        modify_recorder = self.mock_conn.modify_s.side_effect = Recorder()
        for r in 'K-N-O', 'K-N', 'K', None:
            dn = user_dn('userone')
            args_add = ()
            modify_recorder.expect(role_dn(r),
                                   ((ldap.MOD_ADD, 'uniqueMember', [dn]),),
                                   return_value=(ldap.RES_MODIFY, []))
            modify_recorder.expect(role_dn(r),
                                   ((ldap.MOD_DELETE, 'uniqueMember', ['']),),
                                   return_value=(ldap.RES_MODIFY, []))

        self.agent._add_member_dn_to_role_dn(role_dn('K-N-O'),
                                             user_dn('userone'))

        search_recorder.assert_end()
        modify_recorder.assert_end()

class TestRemoveFromRole(unittest.TestCase):
    def setUp(self):
        self.agent = StubbedLdapAgent(ldap_server='')
        self.mock_conn = self.agent.conn

    def test_missing_user(self):
        user_dn = self.agent._user_dn
        role_dn = self.agent._role_dn
        mock_rm = self.agent._remove_member_dn_from_single_role_dn = Mock()
        self.mock_conn.search_s.return_value = []

        self.assertRaises(ValueError,
                          self.agent._remove_member_dn_from_role_dn,
                          role_dn('K-N-O'), user_dn('x'))

        self.mock_conn.search_s.assert_called_once_with(
                user_dn('x'), ldap.SCOPE_BASE, attrlist=())
        assert mock_rm.call_count == 0

    def test_missing_role(self):
        user_dn = self.agent._user_dn
        role_dn = self.agent._role_dn
        mock_rm = self.agent._remove_member_dn_from_single_role_dn = Mock()
        recorder = self.mock_conn.search_s.side_effect = Recorder()
        recorder.expect(user_dn('userone'), ldap.SCOPE_BASE, attrlist=(),
                        return_value=[(user_dn('userone'), {})])
        recorder.expect(role_dn('K-N-X'), ldap.SCOPE_BASE, attrlist=(),
                        return_value=[])

        self.assertRaises(ValueError,
                          self.agent._remove_member_dn_from_role_dn,
                          role_dn('K-N-X'), user_dn('userone'))

        recorder.assert_end()
        assert mock_rm.call_count == 0

    def test_non_member(self):
        user_dn = self.agent._user_dn
        role_dn = self.agent._role_dn
        mock_rm = self.agent._remove_member_dn_from_single_role_dn = Mock()
        recorder = self.mock_conn.search_s.side_effect = Recorder()
        the_filter = ('(&(objectClass=groupOfUniqueNames)'
                      '(uniqueMember=%s))') % user_dn('userone')
        recorder.expect(user_dn('userone'), ldap.SCOPE_BASE, attrlist=(),
                        return_value=[(user_dn('userone'), {})])
        recorder.expect(role_dn('K-N-O'), ldap.SCOPE_BASE, attrlist=(),
                        return_value=[(role_dn('K-N-O'), {})])
        recorder.expect(role_dn('K-N-O'), ldap.SCOPE_SUBTREE, attrlist=(),
                        filterstr=the_filter, return_value=[])

        self.assertRaises(ValueError,
                          self.agent._remove_member_dn_from_role_dn,
                          role_dn('K-N-O'), user_dn('userone'))

        recorder.assert_end()
        assert mock_rm.call_count == 0

    def test_remove(self):
        user_dn = self.agent._user_dn
        role_dn = self.agent._role_dn
        mock_rm = self.agent._remove_member_dn_from_single_role_dn = Mock()
        recorder = self.mock_conn.search_s.side_effect = Recorder()
        the_filter = ('(&(objectClass=groupOfUniqueNames)'
                      '(uniqueMember=%s))') % user_dn('userone')
        recorder.expect(user_dn('userone'), ldap.SCOPE_BASE, attrlist=(),
                        return_value=[(user_dn('userone'), {})])
        recorder.expect(role_dn('K-N'), ldap.SCOPE_BASE, attrlist=(),
                        return_value=[(role_dn('K-N'), {})])
        recorder.expect(role_dn('K-N'), ldap.SCOPE_SUBTREE, attrlist=(),
                        filterstr=the_filter,
                        return_value=[ (role_dn('K-N-O'), {}),
                                       (role_dn('K-N-P'), {}),
                                       (role_dn('K-N-P-Q'), {}),
                                       (role_dn('K-N'), {}) ])

        self.agent._remove_member_dn_from_role_dn(role_dn('K-N'),
                                                  user_dn('userone'))

        recorder.assert_end()
        assert mock_rm.call_args_list == [
            ((user_dn('userone'), role_dn('K-N-P-Q')), {}),
            ((user_dn('userone'), role_dn('K-N-P')), {}),
            ((user_dn('userone'), role_dn('K-N-O')), {}),
            ((user_dn('userone'), role_dn('K-N')), {})]

org_info_fixture = {
    'name': u"Ye olde bridge club",
    'phone': u"555 2222",
    'fax': u"555 9999",
    'url': u"http://bridge.example.com/",
    'address': (u"13 Card games road\n"
                u"K\xf8benhavn, Danmark\n"),
    'street': u"Card games road",
    'po_box': u"123456",
    'postal_code': u"456789",
    'country': u"Denmark",
    'locality': u"K\xf8benhavn",
}

class OrganisationsTest(unittest.TestCase):
    def setUp(self):
        self.agent = StubbedLdapAgent(ldap_server='')
        self.mock_conn = self.agent.conn

    def test_get_organisation(self):
        bridge_club_dn = 'cn=bridge_club,ou=Organisations,o=EIONET,l=Europe'
        self.mock_conn.search_s.return_value = [(bridge_club_dn, {
            'o': ['Ye olde bridge club'],
            'telephoneNumber': ['555 2222'],
            'facsimileTelephoneNumber': ['555 9999'],
            'street': ['Card games road'],
            'postOfficeBox': ['123456'],
            'postalCode': ['456789'],
            'postalAddress': ['13 Card games road\n'
                              'K\xc3\xb8benhavn, Danmark\n'],
            'st': ['Denmark'],
            'l': ['K\xc3\xb8benhavn'],
            'labeledURI': ['http://bridge.example.com/'],
        })]

        org_info = self.agent.org_info('bridge_club')

        self.mock_conn.search_s.assert_called_once_with(
                bridge_club_dn, ldap.SCOPE_BASE)
        self.assertEqual(org_info, dict(org_info_fixture,
                                        dn=bridge_club_dn,
                                        id='bridge_club'))
        for name in org_info_fixture:
            assert type(org_info[name]) is unicode

    def test_create_organisation(self):
        self.agent._bound = True
        self.mock_conn.add_s.return_value = (ldap.RES_ADD, [])

        self.agent.create_org('poker_club', {
            'name': u"P\xf8ker club",
            'url': u"http://poker.example.com/",
        })

        poker_club_dn = 'cn=poker_club,ou=Organisations,o=EIONET,l=Europe'
        self.mock_conn.add_s.assert_called_once_with(poker_club_dn, [
            ('o', ['P\xc3\xb8ker club']),
            ('labeledURI', ['http://poker.example.com/']),
        ])

    def test_delete_organisation(self):
        self.agent._bound = True
        self.mock_conn.delete_s.return_value = (ldap.RES_DELETE, [])
        poker_club_dn = 'cn=poker_club,ou=Organisations,o=EIONET,l=Europe'

        self.agent.delete_org('poker_club')

        self.mock_conn.delete_s.assert_called_once_with(poker_club_dn)

class OrganisationEditTest(unittest.TestCase):
    def setUp(self):
        self.agent = StubbedLdapAgent(ldap_server='')
        self.mock_conn = self.agent.conn
        self.mock_conn.search_s.return_value = [
            ('cn=bridge_club,ou=Organisations,o=EIONET,l=Europe', {
                'o': ['Ye olde bridge club'],
                'labeledURI': ['http://bridge.example.com/'],
             })]
        self.mock_conn.modify_s.return_value = (ldap.RES_MODIFY, [])

    def test_change_nothing(self):
        self.agent.set_org_info('bridge_club', {
            'name': u"Ye olde bridge club",
            'url': u"http://bridge.example.com/",
        })

        assert self.mock_conn.modify_s.call_count == 0

    def test_add_one(self):
        self.agent.set_org_info('bridge_club', {
            'name': u"Ye olde bridge club",
            'url': u"http://bridge.example.com/",
            'phone': u"555 2222",
        })

        bridge_club_dn = 'cn=bridge_club,ou=Organisations,o=EIONET,l=Europe'
        modify_statements = [ (ldap.MOD_ADD, 'telephoneNumber', ['555 2222']) ]
        self.mock_conn.modify_s.assert_called_once_with(
                bridge_club_dn, tuple(modify_statements))

    def test_change_one(self):
        self.agent.set_org_info('bridge_club', {
            'name': u"Ye new bridge club",
            'url': u"http://bridge.example.com/",
        })

        bridge_club_dn = 'cn=bridge_club,ou=Organisations,o=EIONET,l=Europe'
        modify_statements = [ (ldap.MOD_REPLACE, 'o', ['Ye new bridge club']) ]
        self.mock_conn.modify_s.assert_called_once_with(
                bridge_club_dn, tuple(modify_statements))

    def test_remove_one(self):
        self.agent.set_org_info('bridge_club', {
            'url': u"http://bridge.example.com/",
        })

        bridge_club_dn = 'cn=bridge_club,ou=Organisations,o=EIONET,l=Europe'
        modify_statements = [ (ldap.MOD_DELETE, 'o', ['Ye olde bridge club']) ]
        self.mock_conn.modify_s.assert_called_once_with(
                bridge_club_dn, tuple(modify_statements))

    def test_unicode(self):
        self.agent.set_org_info('bridge_club', {
            'name': u"\u0143\xe9w n\xe6\u1e41",
            'url': u"http://bridge.example.com/",
        })

        bridge_club_dn = 'cn=bridge_club,ou=Organisations,o=EIONET,l=Europe'
        modify_statements = [ (ldap.MOD_REPLACE, 'o', [
                '\xc5\x83\xc3\xa9w n\xc3\xa6\xe1\xb9\x81']) ]
        self.mock_conn.modify_s.assert_called_once_with(
                bridge_club_dn, tuple(modify_statements))
