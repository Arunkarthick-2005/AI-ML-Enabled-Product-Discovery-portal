String formatCategory(Map<String, dynamic> category) {
  final levels = [
    category['level_1'],
    category['level_2'],
    category['level_3'],
  ];

  final validLevels = levels
      .where((level) =>
          level != null && level.toString().trim().isNotEmpty)
      .toList();

  return validLevels.join(" > ");
}