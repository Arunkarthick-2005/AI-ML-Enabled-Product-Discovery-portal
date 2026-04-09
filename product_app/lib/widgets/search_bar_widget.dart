import 'package:flutter/material.dart';
import '../screens/search_result_screen.dart';

class SearchBarWidget extends StatelessWidget {
  const SearchBarWidget({super.key});

  @override
  Widget build(BuildContext context) {
    final controller = TextEditingController();

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: TextField(
        controller: controller,
        decoration: const InputDecoration(
          hintText: "Search products...",
          prefixIcon: Icon(Icons.search),
          border: OutlineInputBorder(),
        ),
        onSubmitted: (value) {
          if (value.trim().isEmpty) return;

          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => SearchResultScreen(query: value.trim()),
            ),
          );
        },
      ),
    );
  }
}