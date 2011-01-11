import unittest
from copy import deepcopy

import ldap
from eea.roleseditor import ldap_agent
from mock import Mock, patch, wraps

import fixtures

class LdapAgentWithMock(ldap_agent.LdapAgent):
    def _sub_roles_with_member(self, role_dn, member_dn):
        for dn, attrs in mock_ldap.data.iteritems():
            if dn != role_dn and not dn.endswith(',' + role_dn):
                continue
            if member_dn in attrs.get('uniqueMember', []):
                yield dn

def agent_with_mock_connection(func):
    @patch('ldap.initialize')
    @wraps(func)
    def wrapper(*args):
        mock_ldap_initialize = args[-1]
        mock_conn = Mock()
        mock_ldap_initialize.return_value = mock_conn
        agent = ldap_agent.LdapAgent(ldap_server='ldap2.eionet.europa.eu')
        args = args[:-1] + (agent, mock_conn)
        return func(*args)
    return wrapper

class LdapAgentTest(unittest.TestCase):
    @agent_with_mock_connection
    def test_user_dn_conversion(self, agent, ldap_conn):
        user_values = {
            'usertwo': 'uid=usertwo,ou=Users,o=EIONET,l=Europe',
            'blahsdfsd': 'uid=blahsdfsd,ou=Users,o=EIONET,l=Europe',
            'x': 'uid=x,ou=Users,o=EIONET,l=Europe',
            '12': 'uid=12,ou=Users,o=EIONET,l=Europe',
            '-': 'uid=-,ou=Users,o=EIONET,l=Europe',
        }
        for user_id, user_dn in user_values.iteritems():
            assert agent._user_dn(user_id) == user_dn
            assert agent._user_id(user_dn) == user_id
        bad_user_dns = [
            'asdf',
            'uid=a,cn=xxx,ou=Users,o=EIONET,l=Europe',
            'uid=a,ou=Groups,o=EIONET,l=Europe',
            'a,ou=Users,o=EIONET,l=Europe',
        ]
        for bad_dn in bad_user_dns:
            self.assertRaises(AssertionError, agent._user_id, bad_dn)

    @agent_with_mock_connection
    def test_org_dn_conversion(self, agent, mock_conn):
        org_values = {
            'air_agency': 'cn=air_agency,ou=Organisations,o=EIONET,l=Europe',
            'blahsdfsd': 'cn=blahsdfsd,ou=Organisations,o=EIONET,l=Europe',
            'x': 'cn=x,ou=Organisations,o=EIONET,l=Europe',
            '12': 'cn=12,ou=Organisations,o=EIONET,l=Europe',
            '-': 'cn=-,ou=Organisations,o=EIONET,l=Europe',
        }
        for org_id, org_dn in org_values.iteritems():
            assert agent._org_dn(org_id) == org_dn
            assert agent._org_id(org_dn) == org_id
        bad_org_dns = [
            'asdf',
            'cn=a,cn=xxx,ou=Organisations,o=EIONET,l=Europe',
            'cn=a,ou=Groups,o=EIONET,l=Europe',
            'a,ou=Organisations,o=EIONET,l=Europe',
        ]
        for bad_dn in bad_org_dns:
            self.assertRaises(AssertionError, agent._org_id, bad_dn)

    @agent_with_mock_connection
    def test_role_dn_conversion(self, agent, mock_conn):
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
            assert agent._role_dn(role_id) == role_dn
            assert agent._role_id(role_dn) == role_id
        bad_role_dns = [
            'asdf',
            'a,ou=Users,o=EIONET,l=Europe',
            'cn=aaa-bbb,ou=Roles,o=EIONET,l=Europe',
            'cn=aaa-bbb,cn=bbb,ou=Roles,o=EIONET,l=Europe',
            'cn=cad,cn=aaa-bbb,cn=aaa,ou=Roles,o=EIONET,l=Europe',
            'cn=cad-x-aaa-bbb,cn=aaa-bbb,cn=aaa,ou=Roles,o=EIONET,l=Europe',
        ]
        for bad_dn in bad_role_dns:
            self.assertRaises(AssertionError, agent._role_id, bad_dn)

    @agent_with_mock_connection
    def test_role_names_in_role(self, agent, mock_conn):
        mock_conn.search_s.return_value = [
            ('cn=A,ou=Roles,o=EIONET,l=Europe', {'description': ["Role [A]"]}),
            ('cn=K,ou=Roles,o=EIONET,l=Europe', {'description': ["Role [K]"]})]
        assert agent.role_names_in_role(None) == {'A': "Role [A]",
                                                  'K': "Role [K]"}
        mock_conn.search_s.assert_called_once_with(
           'ou=Roles,o=EIONET,l=Europe', ldap.SCOPE_ONELEVEL,
           attrlist=('description',),
           filterstr='(objectClass=groupOfUniqueNames)')


        mock_conn.search_s = Mock()
        mock_conn.search_s.return_value = [
            ('cn=A-B,cn=A,ou=Roles,o=EIONET,l=Europe',
             {'description': ["Role [A B]"]}),
            ('cn=A-C,cn=A,ou=Roles,o=EIONET,l=Europe',
             {'description': ["Role [A C]"]})]
        assert agent.role_names_in_role('A') == {'A-B': "Role [A B]",
                                                 'A-C': "Role [A C]"}
        mock_conn.search_s.assert_called_once_with(
           'cn=A,ou=Roles,o=EIONET,l=Europe', ldap.SCOPE_ONELEVEL,
           attrlist=('description',),
           filterstr='(objectClass=groupOfUniqueNames)')


        mock_conn.search_s = Mock()
        mock_conn.search_s.return_value = []
        assert agent.role_names_in_role('A-B') == {}
        mock_conn.search_s.assert_called_once_with(
           'cn=A-B,cn=A,ou=Roles,o=EIONET,l=Europe', ldap.SCOPE_ONELEVEL,
           attrlist=('description',),
           filterstr='(objectClass=groupOfUniqueNames)')

    @agent_with_mock_connection
    def test_members_in_role(self, agent, mock_conn):
        role_dn = agent._role_dn
        user_dn = agent._user_dn
        org_dn = agent._org_dn

        calls_list = []
        def mock_called(dn, scope, **kwargs):
            assert kwargs == {'attrlist': ('uniqueMember',),
                              'filterstr': '(objectClass=groupOfUniqueNames)'}
            expected_dn, expected_scope, ret = calls_list.pop(0)
            assert dn == expected_dn
            assert scope == expected_scope
            return ret

        mock_conn.search_s.side_effect = mock_called

        # no local members
        calls_list[:] = [
            (role_dn('A'), ldap.SCOPE_BASE, [
                (role_dn('A'), {'uniqueMember': [ user_dn('userone') ]}),
             ]),
            (role_dn('A'), ldap.SCOPE_ONELEVEL, [
                (role_dn('A-B'), {'uniqueMember': [ user_dn('userone') ]}),
             ]),
        ]
        assert agent.members_in_role('A') == {'users': [], 'orgs': []}
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
        assert agent.members_in_role('A') == {'users': ['userone'], 'orgs': []}
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
        assert agent.members_in_role('A') == {'users': ['userone'],
                                              'orgs': ['air_agency']}
        assert calls_list == [], "not all calls were made"


    @agent_with_mock_connection
    def test_user_info(self, agent, mock_conn):
        mock_conn.search_s.return_value = [
            ('uid=usertwo,ou=Users,o=EIONET,l=Europe', {
                'cn': ['User Two'],
                'mail': ['user_two@example.com'],
                'telephoneNumber': ['555 1234 2'],
                'o': ['Testers Club'],
            })]

        info = agent.user_info('usertwo')
        mock_conn.search_s.assert_called_once_with(
            'uid=usertwo,ou=Users,o=EIONET,l=Europe', ldap.SCOPE_BASE,
            filterstr='(objectClass=organizationalPerson)')

        assert info['name'] == 'User Two'
        assert info['email'] == 'user_two@example.com'
        assert info['phone'] == '555 1234 2'
        assert info['organisation'] == 'Testers Club'

    @agent_with_mock_connection
    def test_user_info_bad_userid(self, agent, mock_conn):
        mock_conn.search_s.return_value = []
        self.assertRaises(AssertionError, agent.user_info, 'nosuchuser')

    @agent_with_mock_connection
    def test_org_info(self, agent, mock_conn):
        mock_conn.search_s.return_value = [
            ('cn=air_agency,ou=Organisations,o=EIONET,l=Europe',
             {'o': ['Agency for Air Studies'],
              'labeledURI': ['http://www.air_agency.example.com']})]
        info = agent.org_info('air_agency')
        mock_conn.search_s.assert_called_once_with(
            'cn=air_agency,ou=Organisations,o=EIONET,l=Europe',
            ldap.SCOPE_BASE)
        assert info['name'] == "Agency for Air Studies"
        assert info['url'] == "http://www.air_agency.example.com"

    @agent_with_mock_connection
    def test_filter_roles(self, agent, mock_conn):
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
        ret = [(agent._role_dn(role_id), {}) for role_id in role_id_list]

        for pattern, expected in expected_results.iteritems():
            mock_conn.search_s = Mock(return_value=deepcopy(ret))
            result = agent.filter_roles(pattern)
            mock_conn.search_s.assert_called_once_with(
                'ou=Roles,o=EIONET,l=Europe', ldap.SCOPE_SUBTREE,
                filterstr='(objectClass=groupOfUniqueNames)', attrlist=())
            assert set(expected) == set(result), \
                   "pattern %r: %r != %r" % (pattern, expected, result)

    @agent_with_mock_connection
    def test_delete_role(self, agent, mock_conn):
        roles_to_delete = ['K', 'K-L', 'K-L-O', 'K-M']
        agent._bound = True
        mock_conn.search_s.return_value = [ (agent._role_dn(r), {}) for r in
                                            roles_to_delete ]
        mock_conn.delete_s.return_value = (ldap.RES_DELETE, [])
        agent.delete_role('K')

        mock_conn.search_s.assert_called_once_with(
            'cn=K,ou=Roles,o=EIONET,l=Europe', ldap.SCOPE_SUBTREE,
            filterstr='(objectClass=groupOfUniqueNames)', attrlist=())

        roles_to_delete.sort()
        roles_to_delete.reverse()
        for args, kwargs in mock_conn.delete_s.call_args_list:
            assert kwargs == {}
            assert args == (agent._role_dn(roles_to_delete.pop(0)),)
        assert roles_to_delete == []

        # TODO: assert error when deleting non-existent role
        # TODO: test deleting top-level role

class TestCreateRole(unittest.TestCase):
    @agent_with_mock_connection
    def test_create(self, agent, mock_conn):
        agent._bound = True
        mock_conn.add_s.return_value=(ldap.RES_ADD, [])
        agent.create_role('A-B-X', "My new test role")
        mock_conn.add_s.assert_called_once_with(
            'cn=A-B-X,cn=A-B,cn=A,ou=Roles,o=EIONET,l=Europe',
            [('objectClass', ['top', 'groupOfUniqueNames']),
             ('ou', ['X']),
             ('uniqueMember', ['']),
             ('description', ['My new test role'])])

    @agent_with_mock_connection
    def test_existing_role(self, agent, mock_conn):
        agent._bound = True
        mock_conn.add_s.side_effect = ldap.NO_SUCH_OBJECT
        self.assertRaises(ValueError, agent.create_role, 'A-C', "blah")

    @agent_with_mock_connection
    def test_missing_parent(self, agent, mock_conn):
        agent._bound = True
        mock_conn.add_s.side_effect = ldap.ALREADY_EXISTS
        self.assertRaises(ValueError, agent.create_role, 'A-X-Y', "blah")

    @agent_with_mock_connection
    def test_empty_description(self, agent, mock_conn):
        agent._bound = True
        mock_conn.add_s.return_value = (ldap.RES_ADD, [])
        agent.create_role('A-B-Z', "")
        mock_conn.add_s.assert_called_once_with(
            'cn=A-B-Z,cn=A-B,cn=A,ou=Roles,o=EIONET,l=Europe',
            [('objectClass',
             ['top', 'groupOfUniqueNames']),
             ('ou', ['Z']),
             ('uniqueMember', [''])])

    @agent_with_mock_connection
    def test_create_top_role(self, agent, mock_conn):
        agent._bound = True
        mock_conn.add_s.return_value = (ldap.RES_ADD, [])
        agent.create_role('T', "top role")
        mock_conn.add_s.assert_called_once_with(
            'cn=T,ou=Roles,o=EIONET,l=Europe',
            [('objectClass', ['top', 'groupOfUniqueNames']),
             ('ou', ['T']),
             ('uniqueMember', ['']),
             ('description', ['top role']),])

class TestAddToRole(unittest.TestCase):
    @agent_with_mock_connection
    def test_missing_user(self, agent, mock_conn):
        user_dn = agent._user_dn
        role_dn = agent._role_dn
        agent._bound = True

        mock_search = mock_conn.search_s
        mock_search.expect(user_dn('x'), ldap.SCOPE_BASE, attrlist=(),
                           return_value=[])

        self.assertRaises(ValueError, agent._add_member_dn_to_role_dn,
                          role_dn('K-N-O'), user_dn('x'))

        mock_search.assert_expect_satisfied()

    @agent_with_mock_connection
    def test_missing_role(self, agent, mock_conn):
        user_dn = agent._user_dn
        role_dn = agent._role_dn
        agent._bound = True

        mock_search = mock_conn.search_s
        mock_search.expect(user_dn('userone'), ldap.SCOPE_BASE, attrlist=(),
                           return_value=[(user_dn('userone'), {})])
        mock_search.expect(role_dn('K-N-X'), ldap.SCOPE_BASE, attrlist=(),
                           return_value=[])

        self.assertRaises(ValueError, agent._add_member_dn_to_role_dn,
                          role_dn('K-N-X'), user_dn('userone'))

        mock_search.assert_expect_satisfied()

    @agent_with_mock_connection
    def test_add(self, agent, mock_conn):
        user_dn = agent._user_dn
        role_dn = agent._role_dn
        agent._bound = True

        mock_search = mock_conn.search_s
        mock_search.expect(user_dn('userone'), ldap.SCOPE_BASE, attrlist=(),
                           return_value=[(user_dn('userone'), {})])
        mock_search.expect(role_dn('K-N-O'), ldap.SCOPE_BASE, attrlist=(),
                           return_value=[(role_dn('K-N-O'), {})])

        mock_modify = mock_conn.modify_s
        for r in 'K-N-O', 'K-N', 'K', None:
            dn = user_dn('userone')
            args_add = ()
            mock_modify.expect(role_dn(r),
                               ((ldap.MOD_ADD, 'uniqueMember', [dn]),),
                               return_value=(ldap.RES_MODIFY, []))
            mock_modify.expect(role_dn(r),
                               ((ldap.MOD_DELETE, 'uniqueMember', ['']),),
                               return_value=(ldap.RES_MODIFY, []))

        agent._add_member_dn_to_role_dn(role_dn('K-N-O'), user_dn('userone'))

        mock_search.assert_expect_satisfied()
        mock_modify.assert_expect_satisfied()

class TestRemoveFromRole(unittest.TestCase):
    @agent_with_mock_connection
    def test_missing_user(self, agent, mock_conn):
        user_dn = agent._user_dn
        role_dn = agent._role_dn
        mock_rm = agent._remove_member_dn_from_single_role_dn = Mock()
        mock_search = mock_conn.search_s
        mock_search.expect(user_dn('x'), ldap.SCOPE_BASE, attrlist=(),
                           return_value=[])

        self.assertRaises(ValueError, agent._remove_member_dn_from_role_dn,
                          role_dn('K-N-O'), user_dn('x'))

        mock_search.assert_expect_satisfied()
        assert mock_rm.call_count == 0

    @agent_with_mock_connection
    @patch('eea.roleseditor.ldap_agent.LdapAgent'
           '._remove_member_dn_from_single_role_dn')
    def test_missing_role(self, agent, mock_conn, mock_rm):
        user_dn = agent._user_dn
        role_dn = agent._role_dn
        mock_rm = agent._remove_member_dn_from_single_role_dn = Mock()
        mock_search = mock_conn.search_s
        mock_search.expect(user_dn('userone'), ldap.SCOPE_BASE, attrlist=(),
                           return_value=[(user_dn('userone'), {})])
        mock_search.expect(role_dn('K-N-X'), ldap.SCOPE_BASE, attrlist=(),
                           return_value=[])

        self.assertRaises(ValueError, agent._remove_member_dn_from_role_dn,
                          role_dn('K-N-X'), user_dn('userone'))

        mock_search.assert_expect_satisfied()
        assert mock_rm.call_count == 0

    @agent_with_mock_connection
    def test_non_member(self, agent, mock_conn):
        user_dn = agent._user_dn
        role_dn = agent._role_dn
        mock_rm = agent._remove_member_dn_from_single_role_dn = Mock()
        mock_search = mock_conn.search_s
        the_filter = ('(&(objectClass=groupOfUniqueNames)'
                      '(uniqueMember=%s))') % user_dn('userone')
        mock_search.expect(user_dn('userone'), ldap.SCOPE_BASE, attrlist=(),
                           return_value=[(user_dn('userone'), {})])
        mock_search.expect(role_dn('K-N-O'), ldap.SCOPE_BASE, attrlist=(),
                           return_value=[(role_dn('K-N-O'), {})])
        mock_search.expect(role_dn('K-N-O'), ldap.SCOPE_SUBTREE, attrlist=(),
                           filterstr=the_filter, return_value=[])

        self.assertRaises(ValueError, agent._remove_member_dn_from_role_dn,
                          role_dn('K-N-O'), user_dn('userone'))

        mock_search.assert_expect_satisfied()
        assert mock_rm.call_count == 0

    @agent_with_mock_connection
    def test_remove(self, agent, mock_conn):
        user_dn = agent._user_dn
        role_dn = agent._role_dn
        mock_rm = agent._remove_member_dn_from_single_role_dn = Mock()
        mock_search = mock_conn.search_s
        the_filter = ('(&(objectClass=groupOfUniqueNames)'
                      '(uniqueMember=%s))') % user_dn('userone')
        mock_search.expect(user_dn('userone'), ldap.SCOPE_BASE, attrlist=(),
                           return_value=[(user_dn('userone'), {})])
        mock_search.expect(role_dn('K-N'), ldap.SCOPE_BASE, attrlist=(),
                           return_value=[(role_dn('K-N'), {})])
        mock_search.expect(role_dn('K-N'), ldap.SCOPE_SUBTREE, attrlist=(),
                           filterstr=the_filter,
                           return_value=[ (role_dn('K-N-O'), {}),
                                          (role_dn('K-N-P'), {}),
                                          (role_dn('K-N-P-Q'), {}),
                                          (role_dn('K-N'), {}) ])

        agent._remove_member_dn_from_role_dn(role_dn('K-N'),
                                             user_dn('userone'))

        mock_search.assert_expect_satisfied()
        assert mock_rm.call_args_list == [
            ((user_dn('userone'), role_dn('K-N-P-Q')), {}),
            ((user_dn('userone'), role_dn('K-N-P')), {}),
            ((user_dn('userone'), role_dn('K-N-O')), {}),
            ((user_dn('userone'), role_dn('K-N')), {})]
