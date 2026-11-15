"""Revertir exige retirar intentos demo sin cuenta antes de restaurar el CHECK."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pedidos", "0002_intento_cobro_y_entrega"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="intentocobro",
            name="intento_destino_fijado",
        ),
        migrations.AddConstraint(
            model_name="intentocobro",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        (
                            "estado__in",
                            [
                                "reservado",
                                "enviando",
                                "pendiente",
                                "incierto",
                                "rechazado",
                                "vencido",
                                "pagado",
                            ],
                        ),
                        _negated=True,
                    ),
                    models.Q(
                        models.Q(("pey_bank_account_id", ""), _negated=True),
                        models.Q(
                            ("cuenta__isnull", False),
                            ("demo_mode", True),
                            _connector="OR",
                        ),
                    ),
                    _connector="OR",
                ),
                name="intento_destino_fijado",
            ),
        ),
    ]
