import 'package:flutter/material.dart';
import '../widgets/auth_text_field.dart';
import '../services/auth_service.dart';
import 'home_screen.dart';
import '../utils/user_session.dart';
import 'register_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final emailController = TextEditingController();
  final passwordController = TextEditingController();
  bool loading = false;

  static const double fieldWidth = 320;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,

      body: LayoutBuilder(
        builder: (context, constraints) {
          return SingleChildScrollView(
            child: ConstrainedBox(
              constraints: BoxConstraints(minHeight: constraints.maxHeight),
              child: Center(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Text(
                        "Welcome to the Product Discovery Portal",
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontSize: 26,
                          fontWeight: FontWeight.bold,
                          color: Colors.blue,
                        ),
                      ),

                      const SizedBox(height: 32),

                      Card(
                        elevation: 6,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: Padding(
                          padding: const EdgeInsets.all(24),
                          child: Column(
                            children: [
                              SizedBox(
                                width: fieldWidth,
                                child: AuthTextField(
                                  label: "Email",
                                  controller: emailController,
                                  prefixIcon: Icons.email_outlined,
                                ),
                              ),

                              const SizedBox(height: 12),

                              SizedBox(
                                width: fieldWidth,
                                child: AuthTextField(
                                  label: "Password",
                                  controller: passwordController,
                                  isPassword: true,
                                  prefixIcon: Icons.lock_outline,
                                ),
                              ),

                              const SizedBox(height: 24),

                              SizedBox(
                                width: fieldWidth,
                                height: 44,
                                child: ElevatedButton(
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: const Color(0xFF2563EB),
                                    foregroundColor: Colors.white,
                                    shape: RoundedRectangleBorder(
                                      borderRadius: BorderRadius.circular(10),
                                    ),
                                  ),
                                  onPressed: loading
                                      ? null
                                      : () async {
                                          setState(() => loading = true);

                                          final AuthResult? result =
                                              await AuthService.login(
                                            emailController.text.trim(),
                                            passwordController.text.trim(),
                                          );

                                          setState(() => loading = false);

                                          if (result == null) {
                                            ScaffoldMessenger.of(context)
                                                .showSnackBar(
                                              const SnackBar(
                                                content:
                                                    Text("Invalid credentials"),
                                              ),
                                            );
                                            return;
                                          }

                                          // ✅ STORE UUID GLOBALLY
                                          UserSession.currentUserId =
                                              result.userId;

                                          // ✅ NAVIGATE USING UUID
                                          Navigator.pushReplacement(
                                            context,
                                            MaterialPageRoute(
                                              builder: (_) => HomeScreen(
                                                userId: result.userId,
                                                username: result.username,
                                              ),
                                            ),
                                          );
                                        },
                                  child: loading
                                      ? const SizedBox(
                                          width: 18,
                                          height: 18,
                                          child: CircularProgressIndicator(
                                            strokeWidth: 2,
                                            color: Colors.white,
                                          ),
                                        )
                                      : const Text(
                                          "Login",
                                          style: TextStyle(fontSize: 16),
                                        ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),

                      const SizedBox(height: 24),

                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Text(
                            "Don’t have an account?",
                            style: TextStyle(color: Colors.grey[700]),
                          ),
                          TextButton(
                            onPressed: () {
                              Navigator.push(
                                context,
                                MaterialPageRoute(
                                  builder: (_) => const RegisterScreen(),
                                ),
                              );
                            },
                            child: const Text("Create one"),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}