# Generated by Django 4.2.11 on 2024-04-19 01:03

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0023_marker"),
    ]

    operations = [
        migrations.CreateModel(
            name="List",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=200)),
                (
                    "replies_policy",
                    models.CharField(
                        choices=[
                            ("followed", "Followed"),
                            ("list", "List Only"),
                            ("none", "None"),
                        ],
                        max_length=10,
                    ),
                ),
                ("exclusive", models.BooleanField()),
                (
                    "identity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lists",
                        to="users.identity",
                    ),
                ),
                (
                    "members",
                    models.ManyToManyField(
                        blank=True, related_name="in_lists", to="users.identity"
                    ),
                ),
            ],
        ),
    ]
