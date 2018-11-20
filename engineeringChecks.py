# import libraries
import bootstrap_rosemeta
from object_synchronization.service.equivalence import EquivalenceSetMaterializer, SchemaEquivalenceMaterializer
from rosemeta.models import SchemaEquivalence, Table
from rosemeta.models import CustomFieldValue
from logical_metadata.models.models_values import PickerFieldValueDiff
from rosemeta.models.enums import CustomFieldType
from django.db import connection

# safe limit
GROUP_SAFE_LIMIT = 100000

# Schema Equivalence check: This is the only function for it
def check_schema_equivalence(checkSummary):
    schema_groups = SchemaEquivalence.objects.all().values_list('group_id', flat=True).distinct()
    for schema_eq_group_id in schema_groups:
        checkSummary.append("Processing schema equivalence group {}".format(schema_eq_group_id))
        schema_ids = SchemaEquivalence.objects.filter(group_id=schema_eq_group_id).values_list('schema_id', flat=True)
        table_groups = EquivalenceSetMaterializer._fetch_groups(Table._meta.db_table, 'schema_obj_id', schema_ids)
        attr_groups = SchemaEquivalenceMaterializer._fetch_attr_groups(schema_ids)
        checkSummary.append("Table equivalences groups: {}".format(len(table_groups)))
        checkSummary.append("Column equivalences groups: {}".format(len(attr_groups)))
        if len(table_groups) < GROUP_SAFE_LIMIT and len(attr_groups) < GROUP_SAFE_LIMIT:
            checkSummary.append("Schema equivalence group {} is ok".format(schema_eq_group_id))
        else:
            checkSummary.append("CAN NOT UPGRADE BECAUSE OF SCHEMA EQUIVALENCE({}) HAS TOO MANY CHILDREN GROUPS".format(schema_eq_group_id))
            return(False,checkSummary)
 
    return (True,checkSummary)

checkSummary = []      
checkRes,checkSummary = check_schema_equivalence(checkSummary)

if checkRes:
    print("flag:0")
else:
    print("flag:1")