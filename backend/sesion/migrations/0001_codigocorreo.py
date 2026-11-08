from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="CodigoCorreo",
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
                ("correo", models.EmailField(max_length=254)),
                (
                    "proposito",
                    models.CharField(
                        choices=[
                            ("alta", "Alta de cuenta"),
                            ("olvido", "Olvido de contraseña"),
                        ],
                        max_length=10,
                    ),
                ),
                ("codigo_hash", models.CharField(max_length=128)),
                (
                    "contrasena_hash",
                    models.CharField(blank=True, default="", max_length=128),
                ),
                ("expira_en", models.DateTimeField()),
                ("usado_en", models.DateTimeField(blank=True, null=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "código por correo",
                "verbose_name_plural": "códigos por correo",
                "indexes": [
                    models.Index(
                        fields=["correo", "proposito", "usado_en"],
                        name="sesion_codi_correo_7f0e8e_idx",
                    ),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="codigocorreo",
            constraint=models.UniqueConstraint(
                condition=models.Q(("usado_en__isnull", True)),
                fields=("correo", "proposito"),
                name="sesion_codigocorreo_vigente_unico",
            ),
        ),
    ]
