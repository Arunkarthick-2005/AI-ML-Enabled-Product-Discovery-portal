import 'package:flutter/material.dart';
import 'login_screen.dart';
import 'product_detail_screen.dart';
import '../widgets/search_bar_widget.dart';
import '../widgets/copilot_button.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Product Copilot'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () => _logout(context),
          ),
        ],
      ),

      body: Column(
        children: [
          const SizedBox(height: 10),
          const SearchBarWidget(),

          const SizedBox(height: 20),
        ],
      ),

      floatingActionButton: const CopilotButton(),
    );
  }

  void _logout(BuildContext context) {
    Navigator.pushAndRemoveUntil(
      context,
      MaterialPageRoute(builder: (_) => const LoginScreen()),
      (route) => false,
    );
  }
}