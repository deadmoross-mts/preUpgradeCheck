# import libraries
# this is a file in one_off_scripts
# this is the main file to get rosemeta access
import bootstrap_rosemeta
from object_synchronization.service.equivalence import EquivalenceSetMaterializer, SchemaEquivalenceMaterializer
from rosemeta.models import SchemaEquivalence, Table
from rosemeta.models import CustomFieldValue
from logical_metadata.models.models_values import PickerFieldValueDiff
from rosemeta.models.enums import CustomFieldType
from django.db import connection

# create output templates
# all clear = green
colGreen = '\x1b[6;30;42m' + '{}' + '\x1b[0m'
# warning = red
colRed = '\x1b[6;30;41m' + '{}' + '\x1b[0m'

# safe limit
GROUP_SAFE_LIMIT = 100000

def check_schema_equivalence(checkSummary):
    schema_groups = SchemaEquivalence.objects.all().values_list('group_id', flat=True).distinct()
    for schema_eq_group_id in schema_groups:
        checkSummary.append("Processing schema equivalence group %d" % schema_eq_group_id)
        schema_ids = SchemaEquivalence.objects.filter(group_id=schema_eq_group_id).values_list('schema_id', flat=True)
        table_groups = EquivalenceSetMaterializer._fetch_groups(Table._meta.db_table, 'schema_obj_id', schema_ids)
        attr_groups = SchemaEquivalenceMaterializer._fetch_attr_groups(schema_ids)
        checkSummary.append("Table equivalences groups:%d" % len(table_groups))
        checkSummary.append("Column equivalences groups:%d" % len(attr_groups))
        if len(table_groups) < GROUP_SAFE_LIMIT and len(attr_groups) < GROUP_SAFE_LIMIT:
            checkSummary.append("Schema equivalence group %d is ok\n" % schema_eq_group_id)
        else:
            checkSummary.append("\nCAN NOT UPGRADE BECAUSE OF SCHEMA EQUIVALENCE(%d) " \
                  "HAS TOO MANY CHILDREN GROUPS" % schema_eq_group_id)
            return(False,checkSummary)
 
    return (True,checkSummary)

def check_picker_unicode(checkSummary):
    cfv_qs = CustomFieldValue.objects.filter(
        otype__in=['schema', 'data', 'table', 'attribute'],
        field__field_type=CustomFieldType.PICKER).select_related('field')
 
    try:
        for cfv in cfv_qs:
            PickerFieldValueDiff(new_value=cfv.value_text, op='migrate')
    except Exception as e:
        checkSummary.append(e.message)
        checkSummary.append("\nCAN NOT UPGRADE DUE TO UNICODE VALUES PRESENT IN CUSTOM " \
              "FIELD VALUE (%d)" % cfv.id)
        return(False,checkSummary)
    return(True,checkSummary)
 
 
def check_custom_fields_duplicate(checkSummary):
    sql = "SELECT oid, field_type, field_id, COUNT(*), array_agg(cfv.id " \
          "ORDER BY cfv" \
          ".id) cfv_ids FROM rosemeta_customfieldvalue cfv JOIN " \
          "rosemeta_customfield cf ON cf.id = cfv.field_id WHERE otype in " \
          "('table', 'schema', 'data', 'attribute') " \
          "AND field_type IN (1, 2, 4, 7) GROUP BY oid, " \
          "field_type, " \
          "field_id HAVING COUNT(*) > 1 ORDER BY 4 DESC;"
 
    cursor = connection.cursor()
    cursor.execute(sql)
    res = cursor.fetchall()
 
    if res:
#        print "\nCAN NOT UPGRADE - DUPLICATE CUSTOM FIELD VALUE RECORDS FOUND"
#        print res
        return(False,checkSummary)
    return(True,checkSummary)
 
 
def run_all_checks(checkSummary):
    r1,checkSummary = check_custom_fields_duplicate(checkSummary)
    r2,checkSummary = check_picker_unicode(checkSummary)
    r3,checkSummary = check_schema_equivalence(checkSummary)
    if r1 and r2 and r3:
        # ok to upgrade
        print("flag:0,check1:{},check2:{},check3:{}".format(str(r1),str(r2),str(r3)))
    else:
        print("flag:1,check1:{},check2:{},check3:{}".format(str(r1),str(r2),str(r3)))
        
    summ = '|'.join(checkSummary)    
    print("Schema Check Summary: {}".format(summ))

checkSummary = []      
run_all_checks(checkSummary)