import 'package:flutter/material.dart';

class SearchBarWidget extends StatelessWidget {
  final void Function(String query)? onSearch;

  const SearchBarWidget({
    super.key,
    this.onSearch,
  });

  @override
  Widget build(BuildContext context) {
    return TextField(
      decoration: InputDecoration(
        hintText: "Search products...",
        prefixIcon: const Icon(Icons.search),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      ),
      onSubmitted: (value) {
        if (onSearch != null && value.trim().isNotEmpty) {
          onSearch!(value.trim());
        }
      },
    );
  }
}