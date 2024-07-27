import pandas as pd
import json
import sys
import os
import django

# Set the DJANGO_SETTINGS_MODULE environment variable
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "datahub.settings")

# Add the project directory to the sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

# Setup Django
django.setup()

from datetime import datetime
from django.db.models import DateField
from django.apps import apps
from gtfs.models import *

# Initialize a dictionary to hold the model field mappings
model_field_mapping = {}

# Get all models from the 'gtfs' app
gtfs_models = apps.get_app_config("gtfs").get_models()

# Iterate over each model and retrieve its field names
for model in gtfs_models:
    model_name = model._meta.model_name
    field_names = [
        field.name
        for field in model._meta.get_fields()
        if field.concrete and not field.many_to_many and field.name != "id"
    ]
    model_field_mapping[model_name] = field_names

# Print the model field mappings (used for debugging)
# print(model_field_mapping["agency"])

# Path to your Excel file
excel_file_path = "./gtfs/fixtures/gtfs/UCR_bus_GTFS_v2024_1.xlsx"

# Mapping of Excel tab names to Django model names and their fields in ../../models.py
# The mapping is: 'excel_tab': (app_name.model_name, model_field_mapping["model_name"])
tab_to_model_mapping = {
    "agency": ("gtfs.agency", model_field_mapping["agency"]),
    "routes": ("gtfs.route", model_field_mapping["route"]),
    "calendar": ("gtfs.calendar", model_field_mapping["calendar"]),
    "calendar_dates": ("gtfs.calendardate", model_field_mapping["calendardate"]),
}


# Read the Excel file
xls = pd.ExcelFile(excel_file_path)

# Maximum number of rows to process from each sheet
# Set to None to process all rows (used for debugging)
max_rows_per_sheet = ""

# Initialize an empty list for fixtures
fixtures = []

# Initialize a counter for primary keys
pk_counter = 1

# Process each sheet in the Excel file
for sheet_name in xls.sheet_names:
    df = pd.read_excel(xls, sheet_name)

    # Limit the number of rows if max_rows_per_sheet is set
    if isinstance(max_rows_per_sheet, (int)) and max_rows_per_sheet != 0:
        df = df.head(max_rows_per_sheet)

    model_info = tab_to_model_mapping.get(sheet_name)

    if model_info:
        model_name, model_fields = model_info
        custom_model_name = model_name.split(".")[1]
        model_class = apps.get_model(app_label="gtfs", model_name=custom_model_name)

        for index, row in df.iterrows():
            fields_data = {}
            # Managing some field format exeptions
            for field in model_fields:
                # Set the field type
                field_type = model_class._meta.get_field(field)
                if isinstance(field_type, DateField):
                    # Convert the string to a date object
                    field_value = row.get(field, None)
                    field_value = (
                        datetime.strptime(str(field_value), "%Y%m%d").date().isoformat()
                        if field_value
                        else None
                    )
                    fields_data[field] = field_value
                else:
                    # Set the field value to the row's value if it exists, else null
                    fields_data[field] = row.get(field, None)

            # Add a fixed field 'feed' with a value of "1234" for 'gtfs.stop' and 'gtfs.route'
            if "feed" in model_fields:
                fields_data["feed"] = "1234"

            fixture = {"model": model_name, "pk": pk_counter, "fields": fields_data}
            fixtures.append(fixture)
            pk_counter += 1  # Increment the pk counter for the next fixture

# Write fixtures to a file
with open("./gtfs/fixtures/gtfs.json", "w") as f:
    json.dump(fixtures, f, ensure_ascii=False, indent=4)
