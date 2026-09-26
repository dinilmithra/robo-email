"""Render Outlook-compatible HTML email reports with embedded charts.

The application owns its canonical report data and HTML template.
"""

import base64
import html
import json
import logging
from io import BytesIO
from pathlib import Path

# Use a non-interactive backend for matplotlib
try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import ticker
except Exception as exc:
    logging.getLogger(__name__).warning(
        "Matplotlib is unavailable for email charts: %s", exc
    )
    plt = None


logger = logging.getLogger(__name__)


class EmailReportGenerator:
    """
    A utility class to generate an Outlook-compatible HTML email report from test data,
    rendering charts as embedded Base64 images.
    """

    @staticmethod
    def _create_chart_image(plot_function, data, title, **kwargs):
        """Render chart data as a Base64-encoded PNG data URI."""
        if not plt:
            return ""
        try:
            fig, ax = plt.subplots(figsize=(6, 4))
            plot_function(fig, ax, data, title, **kwargs)  # Pass fig to plot function
            buf = BytesIO()
            fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0.1)
            plt.close(fig)
            buf.seek(0)
            image_base64 = base64.b64encode(buf.read()).decode("utf-8")
            return f"data:image/png;base64,{image_base64}"
        except Exception as exc:
            logger.warning("Failed to render chart '%s': %s", title, exc)
            return ""

    @staticmethod
    def _plot_test_summary_donut(fig, ax, data, title, **kwargs):
        """Plots the overall test summary as a donut chart with color-coded center text."""
        status_order = ["Passed", "Failed", "Skipped"]
        sizes = []
        for status in status_order:
            value = data.get(status, 0)
            try:
                numeric_value = int(value)
            except (TypeError, ValueError):
                numeric_value = 0
            sizes.append(max(numeric_value, 0))

        # Matplotlib pie raises when all values are zero/invalid.
        if sum(sizes) == 0:
            ax.axis("off")
            fig.text(0.5, 0.95, title, ha="center", va="top", fontsize=12)
            ax.text(
                0.5,
                0.5,
                "No test results available",
                ha="center",
                va="center",
                fontsize=11,
                color="#666666",
                transform=ax.transAxes,
            )
            return

        colors = {"Passed": "#66BB6A", "Failed": "#EF5350", "Skipped": "#FFA726"}

        ax.pie(
            sizes,
            colors=[colors[status] for status in status_order],
            startangle=90,
            wedgeprops=dict(width=0.4),
        )
        centre_circle = plt.Circle((0, 0), 0.60, fc="white")
        ax.add_artist(centre_circle)

        y_pos = 0.2
        ax.text(
            0,
            y_pos,
            f"Passed: {data.get('Passed', 0)}",
            ha="center",
            va="center",
            fontsize=10,
            color=colors["Passed"],
            weight="bold",
        )
        ax.text(
            0,
            0,
            f"Failed: {data.get('Failed', 0)}",
            ha="center",
            va="center",
            fontsize=10,
            color=colors["Failed"],
            weight="bold",
        )
        ax.text(
            0,
            -y_pos,
            f"Skipped: {data.get('Skipped', 0)}",
            ha="center",
            va="center",
            fontsize=10,
            color=colors["Skipped"],
            weight="bold",
        )

        ax.axis("equal")
        fig.text(0.5, 0.95, title, ha="center", va="top", fontsize=12)

    @staticmethod
    def _plot_stacked_bar(fig, ax, data, title, is_horizontal=True, **kwargs):
        """Plot passed, failed, and skipped totals as a stacked bar chart."""
        labels = list(data.keys())
        passed = [v.get("passed", 0) for v in data.values()]
        failed = [v.get("failed", 0) for v in data.values()]
        skipped = [v.get("skipped", 0) for v in data.values()]

        bar_thickness = 0.5
        colors = ["#66BB6A", "#EF5350", "#FFA726"]

        if is_horizontal:
            y_pos = range(len(labels))
            p_bars = ax.barh(
                y_pos, passed, height=bar_thickness, color=colors[0], label="Passed"
            )
            f_bars = ax.barh(
                y_pos,
                failed,
                height=bar_thickness,
                left=passed,
                color=colors[1],
                label="Failed",
            )
            s_bars = ax.barh(
                y_pos,
                skipped,
                height=bar_thickness,
                left=[p + f for p, f in zip(passed, failed)],
                color=colors[2],
                label="Skipped",
            )
            ax.set_yticks(y_pos)
            ax.set_yticklabels(labels)
            ax.invert_yaxis()
            ax.set_xlabel("Number of Tests")
            ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
        else:
            x_pos = range(len(labels))
            p_bars = ax.bar(
                x_pos, passed, width=bar_thickness, color=colors[0], label="Passed"
            )
            f_bars = ax.bar(
                x_pos,
                failed,
                width=bar_thickness,
                bottom=passed,
                color=colors[1],
                label="Failed",
            )
            s_bars = ax.bar(
                x_pos,
                skipped,
                width=bar_thickness,
                bottom=[p + f for p, f in zip(passed, failed)],
                color=colors[2],
                label="Skipped",
            )
            ax.set_xticks(x_pos)
            ax.set_xticklabels(labels)
            ax.set_ylabel("Number of Tests")
            ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))

        fig.text(0.5, 0.95, title, ha="center", va="top", fontsize=12)
        fig.legend(loc="upper center", bbox_to_anchor=(0.5, 0.9), ncol=3, frameon=False)
        fig.subplots_adjust(top=0.8)

        for i, (p, f, s) in enumerate(zip(passed, failed, skipped)):
            if is_horizontal:
                if p > 0:
                    ax.text(
                        p / 2,
                        i,
                        str(p),
                        ha="center",
                        va="center",
                        color="white",
                        fontsize=8,
                    )
                if f > 0:
                    ax.text(
                        p + f / 2,
                        i,
                        str(f),
                        ha="center",
                        va="center",
                        color="white",
                        fontsize=8,
                    )
                if s > 0:
                    ax.text(
                        p + f + s / 2,
                        i,
                        str(s),
                        ha="center",
                        va="center",
                        color="white",
                        fontsize=8,
                    )
            else:
                if p > 0:
                    ax.text(
                        i,
                        p / 2,
                        str(p),
                        ha="center",
                        va="center",
                        color="white",
                        fontsize=8,
                    )
                if f > 0:
                    ax.text(
                        i,
                        p + f / 2,
                        str(f),
                        ha="center",
                        va="center",
                        color="white",
                        fontsize=8,
                    )
                if s > 0:
                    ax.text(
                        i,
                        p + f + s / 2,
                        str(s),
                        ha="center",
                        va="center",
                        color="white",
                        fontsize=8,
                    )


    DEFAULT_PLACEHOLDERS = {
        "title": "__ROBO_EMAIL_TITLE__",
        "summary_chart": "__ROBO_EMAIL_SUMMARY_CHART_CELL__",
        "chart_1": "__ROBO_EMAIL_CHART_1_CELL__",
        "chart_2": "__ROBO_EMAIL_CHART_2_CELL__",
        "chart_3": "__ROBO_EMAIL_CHART_3_CELL__",
        "report_link": "__ROBO_EMAIL_REPORT_LINK__",
        "created_on": "__ROBO_EMAIL_CREATED_ON__",
    }

    DEFAULT_CHART_SPECS = (
        ("chart_1", "group_1_status", "Status by Group 1", True),
        ("chart_2", "group_2_status", "Status by Group 2", False),
        ("chart_3", "group_3_status", "Status by Group 3", True),
    )

    @classmethod
    def _load_template(cls, template_path: Path, placeholders) -> str:
        """Load and validate the caller-supplied Outlook-compatible template."""
        template_path = Path(template_path)
        template = template_path.read_text(encoding="utf-8")
        missing = [
            placeholder
            for placeholder in placeholders.values()
            if placeholder not in template
        ]
        if missing:
            raise ValueError(
                f"Email template {template_path} is missing required "
                f"placeholder(s): {', '.join(missing)}"
            )
        return template

    @staticmethod
    def _chart_cell(img_src: str, alt_text: str) -> str:
        """Return an Outlook-safe chart cell or a plain fallback cell."""
        safe_alt = html.escape(alt_text, quote=True)
        if img_src:
            safe_src = html.escape(img_src, quote=True)
            return (
                '<td align="center" style="padding: 10px; width: 50%;">'
                f'<img src="{safe_src}" alt="{safe_alt}" '
                'style="max-width: 380px; height: auto;" />'
                "</td>"
            )
        return (
            '<td align="center" style="padding: 10px; width: 50%;">'
            f"{safe_alt} chart not available"
            "</td>"
        )

    @classmethod
    def generate_email_content(
        cls,
        data,
        *,
        template_path: Path,
        placeholders=None,
        chart_specs=None,
    ):
        """Render an Outlook-compatible email body from canonical report data.

        Applications provide their own template and can map any three grouped
        status charts into the reusable chart slots.
        """
        placeholders = dict(placeholders or cls.DEFAULT_PLACEHOLDERS)
        chart_specs = tuple(chart_specs or cls.DEFAULT_CHART_SPECS)
        chart_data = data.get("chart_data") or {}
        summary_data = chart_data.get(
            "test_status_summary", {"Passed": 0, "Failed": 0, "Skipped": 0}
        )

        summary_chart_img = cls._create_chart_image(
            cls._plot_test_summary_donut, summary_data, "Test Summary"
        )

        chart_cells = {}
        for slot, data_key, title, is_horizontal in chart_specs:
            image = cls._create_chart_image(
                cls._plot_stacked_bar,
                chart_data.get(data_key, {}),
                title,
                is_horizontal=is_horizontal,
            )
            chart_cells[slot] = cls._chart_cell(image, title)

        title = html.escape(str(data.get("title", "Test Report")), quote=True)
        report_link = html.escape(str(data.get("report_link", "#")), quote=True)
        created_on = html.escape(
            str(data.get("summary", {}).get("Report Created On", "N/A")),
            quote=True,
        )

        replacements = {
            placeholders["title"]: title,
            placeholders["summary_chart"]: cls._chart_cell(
                summary_chart_img, "Test Summary"
            ),
            placeholders["report_link"]: report_link,
            placeholders["created_on"]: created_on,
        }
        for slot, _, _, _ in chart_specs:
            replacements[placeholders[slot]] = chart_cells[slot]

        rendered = cls._load_template(template_path, placeholders)
        for placeholder, value in replacements.items():
            rendered = rendered.replace(placeholder, value)
        return rendered

    @classmethod
    def generate_from_json(
        cls,
        json_path: Path,
        *,
        template_path: Path,
        placeholders=None,
        chart_specs=None,
    ) -> str:
        """Render the email body from a persisted canonical JSON report."""
        data = json.loads(Path(json_path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Report JSON must contain an object: {json_path}")
        return cls.generate_email_content(
            data,
            template_path=template_path,
            placeholders=placeholders,
            chart_specs=chart_specs,
        )

    @classmethod
    def generate_and_save(
        cls,
        data,
        *,
        template_path: Path,
        filename="email-body.html",
        placeholders=None,
        chart_specs=None,
    ):
        """Render and save an email body from canonical report data."""
        content = cls.generate_email_content(
            data,
            template_path=template_path,
            placeholders=placeholders,
            chart_specs=chart_specs,
        )
        Path(filename).write_text(content, encoding="utf-8")
        logger.info("Email HTML report successfully saved to: %s", filename)
        return filename

    @classmethod
    def generate_from_json_and_save(
        cls,
        json_path: Path,
        *,
        template_path: Path,
        filename="email-body.html",
        placeholders=None,
        chart_specs=None,
    ):
        """Render and save an email body from persisted report JSON."""
        content = cls.generate_from_json(
            json_path,
            template_path=template_path,
            placeholders=placeholders,
            chart_specs=chart_specs,
        )
        Path(filename).write_text(content, encoding="utf-8")
        logger.info("Email HTML report rendered from %s and saved to %s", json_path, filename)
        return filename
