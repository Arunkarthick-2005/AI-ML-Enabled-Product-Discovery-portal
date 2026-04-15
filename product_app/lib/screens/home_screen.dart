import 'package:flutter/material.dart';
import 'login_screen.dart';
import '../widgets/search_bar_widget.dart';
import '../widgets/copilot_button.dart';

class HomeScreen extends StatelessWidget {
  final String username;

  const HomeScreen({
    super.key,
    required this.username,
  });

  @override
  Widget build(BuildContext context) {
    final screenWidth = MediaQuery.of(context).size.width;
    final searchBarWidth =
        screenWidth > 600 ? 500.0 : screenWidth * 0.9;

    return Scaffold(
      appBar: AppBar(
        titleSpacing: 16,
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Product Discovery Portal',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              'Welcome, $username',
              style: const TextStyle(
                fontSize: 13,
                color: Colors.white70,
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () => _logout(context),
          ),
        ],
      ),

      body: Column(
        children: [
          const SizedBox(height: 24),

          Center(
            child: SizedBox(
              width: searchBarWidth,
              child: const SearchBarWidget(),
            ),
          ),

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