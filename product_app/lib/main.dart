import 'package:flutter/material.dart';
import 'screens/login_screen.dart';

void main() {
    runApp(const ProductCopilotApp());
}

class ProductCopilotApp extends StatelessWidget {
  const ProductCopilotApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Product Copilot',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(primarySwatch: Colors.indigo),
      home: const LoginScreen(),
    );
  }
}