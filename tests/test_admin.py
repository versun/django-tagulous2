"""
Tagulous test: Admin

Modules tested:
    tagulous.admin
"""
from __future__ import absolute_import
import re

import django
from django.contrib import admin
from django.contrib import messages
from django.contrib.messages.storage.fallback import CookieStorage
from django.http import QueryDict

from tests.lib import *


MOCK_PATH = 'mock/path'
class MockRequest(object):
    def __init__(self, GET=None, POST=None):
        self.GET = GET or QueryDict('')
        self.POST = POST or QueryDict('')
        self.COOKIES = {}
        self.META = {}
        self._messages = CookieStorage(self)
        self.resolver_match = None
        
    def get_full_path(self):
        return MOCK_PATH
request = MockRequest()


def _monkeypatch_modeladmin():
    """
    ModelAdmin changes between django versions.
    
    Monkeypatch it where necessary to allow tests to function, without making
    any changes to ModelAdmin which would affect the code being tested.
    """
    # Ensure ModelAdmin has get_list_filter - missing in Django 1.4
    # Only used in tests
    # ++ Can be removed once 1.4 support is dropped
    if not hasattr(admin.ModelAdmin, 'get_list_filter'):
        if django.VERSION >= (1, 5):
            raise AttributeError(
                'Only old versions of django are supposed to be missing '
                'ModelAdmin.get_list_filter'
            )
        admin.ModelAdmin.get_list_filter = lambda self, request: self.list_filter
_monkeypatch_modeladmin()


###############################################################################
####### Admin registration
###############################################################################

class AdminRegisterTest(TagTestManager, TestCase):
    """
    Test Admin registration of tagged model
    """
    def setUpExtra(self):
        self.admin = test_admin.SimpleMixedTestAdmin
        self.model = test_models.SimpleMixedTest
        self.model_singletag = self.model.singletag.tag_model
        self.model_tags = self.model.tags.tag_model
        self.site = admin.AdminSite(name='tagulous_admin')
        
    def test_register_site(self):
        "Check register with site"
        self.assertFalse(self.model in self.site._registry)
        tag_admin.register(self.model, self.admin, site=self.site)
        self.assertTrue(self.model in self.site._registry)
        ma = self.site._registry[self.model]
        self.assertIsInstance(ma, tag_admin.TaggedModelAdmin)
    
    def test_register_no_site(self):
        "Check register without site"
        # Replace admin.site with our own
        old_admin_site = admin.site
        admin.site = self.site
        self.assertFalse(self.model in self.site._registry)
        tag_admin.register(self.model, self.admin)
        self.assertTrue(self.model in self.site._registry)
        ma = self.site._registry[self.model]
        self.assertIsInstance(ma, tag_admin.TaggedModelAdmin)
        
        # Return admin.site
        admin.site = old_admin_site
    
    def test_register_models(self):
        "Check register refuses multple models"
        with self.assertRaises(exceptions.ImproperlyConfigured) as cm:
            tag_admin.register([self.model, self.model], self.admin, site=self.site)
        self.assertEqual(
            str(cm.exception),
            'Tagulous can only register a single model with admin.',
        )
        self.assertFalse(self.model in self.site._registry)
        
    def test_register_auto(self):
        "Check register without admin dynamically creates admin class"
        self.assertFalse(self.model in self.site._registry)
        tag_admin.register(self.model, site=self.site)
        self.assertTrue(self.model in self.site._registry)
        ma = self.site._registry[self.model]
        self.assertIsInstance(ma, tag_admin.TaggedModelAdmin)
    
    def test_register_options(self):
        "Check register with options dynamically creates admin class"
        self.assertFalse(self.model in self.site._registry)
        tag_admin.register(
            self.model, self.admin, site=self.site,
            list_display=['name']
        )
        self.assertTrue(self.model in self.site._registry)
        ma = self.site._registry[self.model]
        self.assertIsInstance(ma, tag_admin.TaggedModelAdmin)
        self.assertItemsEqual(
            ma.get_list_display(request),
            ['name'],
        )

    def test_register_tag_descriptor(self):
        "Check register tag descriptor creates correct admin class"
        self.assertFalse(self.model_singletag in self.site._registry)
        tag_admin.register(self.model.singletag, self.admin, site=self.site)
        self.assertTrue(self.model_singletag in self.site._registry)
        ma = self.site._registry[self.model_singletag]
        self.assertIsInstance(ma, tag_admin.TagModelAdmin)

    def test_register_tag_model(self):
        "Check register tag model creates correct admin class"
        self.assertFalse(self.model_singletag in self.site._registry)
        tag_admin.register(self.model_singletag, site=self.site)
        self.assertTrue(self.model_singletag in self.site._registry)
        ma = self.site._registry[self.model_singletag]
        self.assertIsInstance(ma, tag_admin.TagModelAdmin)
    
    def test_register_tag_tree_model(self):
        "Check register tag tree model creates correct admin class"
        tag_model = test_models.TreeTest.tags.tag_model
        self.assertFalse(tag_model in self.site._registry)
        tag_admin.register(tag_model, site=self.site)
        self.assertTrue(tag_model in self.site._registry)
        ma = self.site._registry[tag_model]
        self.assertIsInstance(ma, tag_admin.TagModelAdmin)
    
    def test_tag_model_deprecated(self):
        "Check tag_model still works, but raises warning"
        self.assertFalse(self.model_singletag in self.site._registry)
        
        # Assert it raises a warning
        import warnings
        with warnings.catch_warnings(record=True) as cw:
            warnings.simplefilter("always")
            tag_admin.tag_model(self.model_singletag, site=self.site)
            self.assertEqual(len(cw), 1)
            self.assertTrue(issubclass(cw[-1].category, DeprecationWarning))
            self.assertEqual(
                str(cw[-1].message),
                'tag_model deprecated, use register instead',
            )
        
        # But it should still work
        self.assertTrue(self.model_singletag in self.site._registry)
        ma = self.site._registry[self.model_singletag]
        self.assertIsInstance(ma, tag_admin.TagModelAdmin)
        

###############################################################################
####### Tagged ModelAdmin
###############################################################################

class TaggedAdminTest(TagTestManager, TestCase):
    """
    Test ModelAdmin enhancements
    """
    def setUpExtra(self):
        self.admin = test_admin.SimpleMixedTestAdmin
        self.model = test_models.SimpleMixedTest
        self.model_singletag = self.model.singletag.tag_model
        self.model_tags = self.model.tags.tag_model
        self.site = admin.AdminSite(name='tagulous_admin')
        tag_admin.register(self.model, self.admin, site=self.site)
        self.ma = self.site._registry[self.model]
        self.cl = None
    
    def get_changelist(self, req=request):
        list_display = self.ma.get_list_display(req)
        list_display_links = self.ma.get_list_display_links(req, list_display)
        list_filter = self.ma.get_list_filter(req)
        ChangeList = self.ma.get_changelist(req)
        self.cl = ChangeList(req, self.model, list_display,
            list_display_links, list_filter, self.ma.date_hierarchy,
            self.ma.search_fields, self.ma.list_select_related,
            self.ma.list_per_page, self.ma.list_max_show_all, self.ma.list_editable,
            self.ma
        )
        return self.cl
        
    def get_changelist_results(self, req=request):
        self.get_changelist(req)
        results = self.cl.get_results(req)
        return self.cl.result_list
    
    
    #
    # Tests
    #
    
    def test_changelist_display(self):
        "Check display fields have registered ok and return valid values"
        t1 = self.model.objects.create(name='Test 1', singletag='Mr', tags='red, blue')
        self.assertItemsEqual(
            self.ma.get_list_display(request),
            ['name', 'singletag', '_tagulous_display_tags'],
        )
        results = self.get_changelist_results()
        self.assertEqual(len(results), 1)
        r1 = results[0]
        self.assertEqual(t1.pk, r1.pk)
        
        # Find what it's showing
        from django.contrib.admin.templatetags.admin_list import items_for_result
        row = [
            list(items_for_result(self.cl, result, None))
            for result in results
        ][0]
        self.assertItemsEqual(row, [
            u'<td>Test 1</td>',
            u'<td class="nowrap">Mr</td>',
            u'<td>blue, red</td>',
        ])
    
    def test_changelist_filter(self):
        t1 = self.model.objects.create(name='Test 1', singletag='Mr', tags='red, blue')
        t2 = self.model.objects.create(name='Test 2', singletag='Mrs', tags='red, green')
        t3 = self.model.objects.create(name='Test 3', singletag='Mr', tags='green, blue')
        
        # Check filters are listed
        self.assertItemsEqual(
            self.ma.get_list_filter(request),
            ['singletag', 'tags'],
        )
        
        # Filter by singletag
        singletag_request = MockRequest(GET={
            'singletag__id__exact': self.model_singletag.objects.get(name='Mr').pk,
        })
        results = sorted(
            self.get_changelist_results(singletag_request),
            key=lambda r: r.name
        )
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].pk, t1.pk)
        self.assertEqual(results[1].pk, t3.pk)
        
        # Filter by tag
        tag_request = MockRequest(GET={
            'tags__id__exact': self.model_tags.objects.get(name='green').pk,
        })
        results = sorted(
            self.get_changelist_results(tag_request),
            key=lambda r: r.name
        )
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].pk, t2.pk)
        self.assertEqual(results[1].pk, t3.pk)
    
    def test_form_fields(self):
        "Check forms get the correct widget"
        db_singletag = self.model._meta.get_field('singletag')
        field_singletag = self.ma.formfield_for_dbfield(db_singletag)
        self.assertIsInstance(field_singletag.widget, tag_forms.AdminTagWidget)
        
        db_tags = self.model._meta.get_field('tags')
        field_tags = self.ma.formfield_for_dbfield(db_tags)
        self.assertIsInstance(field_tags.widget, tag_forms.AdminTagWidget)


###############################################################################
####### Tag ModelAdmin
###############################################################################

class TagAdminTest(TagTestManager, TestCase):
    """
    Test Admin registration of a tag model
    """
    def setUpExtra(self):
        self.tagged_model = test_models.SimpleMixedTest
        self.model = self.tagged_model.tags.tag_model
        self.site = admin.AdminSite(name='tagulous_admin')
        tag_admin.register(self.model, site=self.site)
        self.ma = self.site._registry[self.model]
        self.cl = None
        
        # Monkeypatch urls to add in modeladmin
        try:
            from django.conf.urls import include, patterns, url
        except ImportError:
            from django.conf.urls.defaults import include, patterns, url
        self.old_urls = test_urls.urlpatterns
        test_urls.urlpatterns += patterns(
            '',
            url(r'^tagulous_tests_app/admin/', include(self.site.urls)),
        )
        
    def tearDownExtra(self):
        test_urls.urlpatterns = self.old_urls
    
    def get_changelist(self, req=request):
        list_display = self.ma.get_list_display(req)
        list_display_links = self.ma.get_list_display_links(req, list_display)
        list_filter = self.ma.get_list_filter(req)
        ChangeList = self.ma.get_changelist(req)
        self.cl = ChangeList(req, self.model, list_display,
            list_display_links, list_filter, self.ma.date_hierarchy,
            self.ma.search_fields, self.ma.list_select_related,
            self.ma.list_per_page, self.ma.list_max_show_all, self.ma.list_editable,
            self.ma
        )
        return self.cl
    
    def get_cl_queryset(self, cl, request):
        "Because ModelAdmin.get_query_set is deprecated in 1.6"
        if hasattr(cl, 'get_queryset'):
            return cl.get_queryset(request)
        return cl.get_query_set(request)
    
    def populate(self):
        self.o1 = self.tagged_model.objects.create(
            name='Test 1', singletag='Mr', tags='red, blue',
        )
        self.o2 = self.tagged_model.objects.create(
            name='Test 2', singletag='Mrs', tags='red, green',
        )
        self.o3 = self.tagged_model.objects.create(
            name='Test 3', singletag='Mr', tags='green, blue',
        )
        self.red = self.model.objects.get(name='red')
        self.blue = self.model.objects.get(name='blue')
        self.green = self.model.objects.get(name='green')
        
    def assertContains(self, content, *seeks):
        for seek in seeks:
            self.assertTrue(seek in content, msg='Missing %s' % seek)
    
    def assertNotContains(self, content, *seeks):
        for seek in seeks:
            self.assertFalse(seek in content, msg='Unexpected %s' % seek)
    
    
    #
    # Tests
    #
    
    def test_merge_action(self):
        "Check merge_tags action exists"
        self.assertTrue('merge_tags' in self.ma.actions)
        actions = self.ma.get_actions(request)
        self.assertTrue('merge_tags' in actions)
        self.assertTrue(hasattr(actions['merge_tags'][0], '__call__'))
        self.assertEqual(actions['merge_tags'][1], 'merge_tags')
        self.assertEqual(actions['merge_tags'][2], 'Merge selected tags...')
    
    def test_merge_form_empty(self):
        "Check the merge_tags action fails when no tags selected"
        request = MockRequest(POST=QueryDict('action=merge_tags'))
        cl = self.get_changelist(request)
        response = self.ma.response_action(request, self.get_cl_queryset(cl, request))
        msgs = list(messages.get_messages(request))
        
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].message, (
            'Items must be selected in order to perform actions on them. No '
            'items have been changed.'
        ))
        self.assertEqual(response, None)
        
    def test_merge_form_one(self):
        "Check the merge_tags action fails when only one tag selected"
        self.populate()
        request = MockRequest(POST=QueryDict(
            'action=merge_tags&%s=%s' % (admin.ACTION_CHECKBOX_NAME, self.red.pk)
        ))
        cl = self.get_changelist(request)
        response = self.ma.response_action(request, self.get_cl_queryset(cl, request))
        msgs = list(messages.get_messages(request))

        self.assertEqual(len(msgs), 1)
        self.assertEqual(
            msgs[0].message, 'You must select at least two tags to merge'
        )
        self.assertTrue('Location: %s' % MOCK_PATH in str(response))

    def test_merge_form_two(self):
        "Check the merge_tags form when two tag selected"
        self.populate()
        request = MockRequest(POST=QueryDict('&'.join(
            ['action=merge_tags'] + [
                '%s=%s' % (admin.ACTION_CHECKBOX_NAME, pk)
                for pk in [self.red.pk, self.green.pk]
            ]
        )))
        cl = self.get_changelist(request)
        response = self.ma.response_action(request, self.get_cl_queryset(cl, request))
        msgs = list(messages.get_messages(request))
        
        # Check response is appropriate
        # ++ This would be a lot easier with assertInHTML, after 1.4 is dropped
        # ++ For now, it's just a mess.
        self.assertEqual(len(msgs), 0)
        content = str(response)
        content_form = content[
            content.index('<form ') : content.index('</form>') + 7
        ]
        self.assertHTMLEqual(
            content_form[:content_form.index('<option')],
            (
                '<form action="" method="POST">'
                '<p><label for="id_merge_to">Merge to:</label>'
                '<select id="id_merge_to" name="merge_to">'
            )
        )
        
        # Can't be sure of options order
        options_raw = content_form[
            content_form.index('<option') : content_form.index('</select>')
        ]
        option1 = options_raw[:options_raw.index('<option', 1)]
        option2 = options_raw[len(option1):options_raw.index('<option', len(option1)+1)]
        option3 = options_raw[len(option1) + len(option2):]
        options = [option.strip() for option in [option1, option2, option3]]
        self.assertTrue(
            '<option value="" selected="selected">---------</option>' in options
        )
        self.assertTrue(
            '<option value="%d">%s</option>' % (self.red.pk, self.red.name) in options
        )
        self.assertTrue(
            '<option value="%d">%s</option>' % (self.green.pk, self.green.name) in options
        )
        
        # Check _selected_action input tags
        inputs_raw = content_form[
            # First input, convenient
            content_form.index('<input') : content_form.index('<div>')
        ]
        input1 = inputs_raw[:inputs_raw.index('<input', 1)]
        input2 = inputs_raw[len(input1):]
        inputs = [
            # Some versions of django may insert a </p> here.
            input_tag.replace('</p>', '').strip()
            for input_tag in [input1, input2]
        ]
        self.assertTrue(any('id="id__selected_action_0"' in i for i in inputs))
        self.assertTrue(any('id="id__selected_action_1"' in i for i in inputs))
        for input_tag in inputs:
            input_tag = re.sub(
                'id__selected_action_\d', 'id__selected_action_x', input_tag,
            )
            expected = (
                '<input id="id__selected_action_x" type="hidden"'
                ' name="_selected_action" value="%d" />'
            )
            try:
                self.assertHTMLEqual(input_tag, expected % self.red.pk)
            except AssertionError:
                self.assertHTMLEqual(input_tag, expected % self.green.pk)
        
        # Check end of form
        self.assertHTMLEqual(
            content_form[
                content_form.index('<div>') : content_form.index('</div>')
            ], (
                '<div>'
                '<input type="submit" name="merge" value="Merge tags">'
                '<input class="default" type="hidden" name="action"'
                ' value="merge_tags">'
                '</div>'
            )
        )
        
        # And just confirm blue wasn't there
        self.assertNotContains(
            content,
            '<option value="%d">%s</option>' % (self.blue.pk, self.blue.name),
        )
    
    def test_merge_form_submit(self):
        self.populate()
        request = MockRequest(POST=QueryDict('&'.join(
            [
                # Submitting
                'action=merge_tags',
                'merge=Merge%%20Tags',
            ] + [
                # These were selected on the changelist, the ones we're merging
                '%s=%s' % (admin.ACTION_CHECKBOX_NAME, pk)
                for pk in [self.red.pk, self.green.pk]
            ] + [
                # This is the one we're merging to
                'merge_to=%s' % self.red.pk,
            ]
        )))
        cl = self.get_changelist(request)
        response = self.ma.response_action(request, self.get_cl_queryset(cl, request))
        msgs = list(messages.get_messages(request))
        
        # Check response is appropriate
        self.assertEqual(len(msgs), 1)
        self.assertEqual(
            msgs[0].message, 'Tags merged'
        )
        self.assertTrue('Location: %s' % MOCK_PATH in str(response))