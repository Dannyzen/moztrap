from tastypie.resources import ALL, ALL_WITH_RELATIONS
from tastypie import fields
from tastypie.resources import ModelResource

from django.http import HttpResponse

from .models import CaseVersion, Case, Suite, CaseStep, SuiteCase
from ..environments.api import EnvironmentResource
from ..core.api import (ProductResource, ProductVersionResource,
                        ReportResultsAuthorization, MTApiKeyAuthentication)
from ..tags.api import TagResource



class SuiteResource(ModelResource):


    class Meta:
        queryset = Suite.objects.all()
        fields = ["name"]
        filtering = {
            "name": ALL,
            }



class CaseResource(ModelResource):
    suites = fields.ToManyField(SuiteResource, "suites", full=True)
    product = fields.ForeignKey(ProductResource, "product")
    class Meta:
        queryset = Case.objects.all()
        fields= ["id", "suites"]
        filtering = {
            "suites": ALL_WITH_RELATIONS,
            }



class CaseStepResource(ModelResource):
    caseversion = fields.ForeignKey(
        "moztrap.model.library.api.CaseVersionResource",
        "caseversion",
        )


    class Meta:
        queryset = CaseStep.objects.all()
        fields = ["number", "instruction", "expected"]



class CaseVersionResource(ModelResource):

    case = fields.ForeignKey(CaseResource, "case", full=True)
    steps = fields.ToManyField(CaseStepResource, "steps", full=True)
    environments = fields.ToManyField(EnvironmentResource, "environments", full=True)
    productversion = fields.ForeignKey(ProductVersionResource, "productversion")
    tags = fields.ToManyField(TagResource, "tags", full=True)


    class Meta:
        queryset = CaseVersion.objects.all()
        list_allowed_methods = ["get", "put", "post"]
        fields = ["id", "name", "description", "case"]
        filtering = {
            "environments": ALL,
            "productversion": ALL_WITH_RELATIONS,
            "case": ALL_WITH_RELATIONS,
            "tags": ALL_WITH_RELATIONS,
            }
        authentication = MTApiKeyAuthentication()
        authorization = ReportResultsAuthorization()




class SuiteCaseSelectionResource(ModelResource):
    """
    Specialty end-point for an AJAX call in the Suite form multi-select widget
    for selecting cases.
    """

    case = fields.ForeignKey(CaseResource, "case")
    productversion = fields.ForeignKey(ProductVersionResource, "productversion")
    tags = fields.ToManyField(TagResource, "tags", full=True)

    class Meta:
        queryset = CaseVersion.objects.filter(latest=True).select_related(
            "case",
            "productversion",
            )
        # @@@ Django 1.4 - use prefetch_related on the tag field
        list_allowed_methods = ['get']
        fields = ["id", "name"]
        filtering = {
            "productversion": ALL_WITH_RELATIONS,
            }

    def get_list(self, request, **kwargs):
        """
        Save the suitecases orders so we don't have to query for each case.

        @@@ Django 1.4 - shouldn't need this when we have prefetch_related
        in Django 1.4
        """
        if "for_suite" in request.GET.keys():
             sc = SuiteCase.objects.filter(suite__id=request.GET["for_suite"])
             self.suitecases_cache = dict((x.case_id, x.order) for x in sc)
        return super(SuiteCaseSelectionResource, self).get_list(
            request, **kwargs)


    def dehydrate(self, bundle):
        """Add some convenience fields to the return JSON."""

        case = bundle.obj.case
        bundle.data["case_id"] = unicode(case.id)
        bundle.data["product_id"] = unicode(case.product_id)
        bundle.data["product"] = {"id": unicode(case.product_id)}

        try:
            bundle.data["created_by"] = {
                "id": unicode(case.created_by.id),
                "username": case.created_by.username,
                }
        except AttributeError:
            bundle.data["created_by"] = None

        try:
            bundle.data["order"] = self.suitecases_cache[case.id]
        except (KeyError, TypeError, AttributeError):
            # suitecases_cache may not be defined, or may be none
            # or may just not contain the id we're looking for.
            # either way, set it to None
            bundle.data["order"] = None

        return bundle


    def create_response(self, request, data, response_class=HttpResponse, **response_kwargs):
        """
        Remove the "cached" runsuites because we're done with it.

        @@@ Django 1.4 - shouldn't need this when we have prefetch_related
        in Django 1.4
        """
        self.suitecases_cache = None
        return super(SuiteCaseSelectionResource, self).create_response(
            request, data, response_class=HttpResponse, **response_kwargs)


    def alter_list_data_to_serialize(self, request, data):
        """Split list of cases between included and excluded from the suite"""
        included = [x for x in data["objects"] if x.data["order"] is not None]
        included = sorted(included, key=lambda k: k.data["order"])
        excluded =  [x for x in data["objects"] if x.data["order"] is None]
        data["objects"] = {"selected": included, "unselected": excluded}
        return data