from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("vmlc", "0002_alter_staff_role"),
    ]

    operations = [
        migrations.RenameField(
            model_name="userverification",
            old_name="profile_photo",
            new_name="face_id",
        ),
    ]