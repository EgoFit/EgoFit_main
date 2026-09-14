from __future__ import annotations

from home.utils import format_duration as format_total_duration


class SeriesMixin:
    def get_total_episodes_and_duration(self, series):
        seasons = series.seasons.prefetch_related("episodes").all()

        total_duration_seconds = 0
        total_episodes_count = 0
        for season in seasons:
            episodes = list(season.episodes.all())
            total_duration_seconds += sum(episode.get_duration_in_seconds() for episode in episodes)
            total_episodes_count += len(episodes)

        return total_episodes_count, self.format_duration(total_duration_seconds)

    def format_duration(self, total_seconds):
        return format_total_duration(total_seconds)

