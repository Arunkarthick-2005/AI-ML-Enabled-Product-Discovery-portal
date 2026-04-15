import 'dart:convert';
import 'package:http/http.dart' as http;

/// ✅ Result object returned after successful login
class AuthResult {
  final String token;
  final String username;

  AuthResult({
    required this.token,
    required this.username,
  });
}

class AuthService {
  static const String baseUrl = "http://localhost:8000";

  // -----------------------------
  // ✅ REGISTER (unchanged)
  // -----------------------------
  static Future<String?> register(
    String name,
    String email,
    String mobile,
    String password,
  ) async {
    try {
      final response = await http.post(
        Uri.parse("$baseUrl/auth/register"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({
          "name": name,
          "email": email,
          "mobile": mobile,
          "password": password,
        }),
      );

      if (response.statusCode == 200 ||
          response.statusCode == 201) {
        return null;
      }

      final data = jsonDecode(response.body);
      return data["detail"] ?? "Registration failed";
    } catch (_) {
      return "Server connection error";
    }
  }

  // -----------------------------
  // ✅ LOGIN (UPDATED + FIXED)
  // -----------------------------
  static Future<AuthResult?> login(
  String email,
  String password,
) async {
  try {
    final response = await http.post(
      Uri.parse("$baseUrl/auth/login"),
      headers: {"Content-Type": "application/json"},
      body: jsonEncode({
        "email": email,
        "password": password,
      }),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);

      final token = data["access_token"];
      if (token == null) return null;

      // ✅ SAFE username extraction
      String username = "User"; // fallback

      if (data.containsKey("user") && data["user"] != null) {
        username = data["user"]["name"] ?? username;
      } else if (data.containsKey("name")) {
        username = data["name"];
      }

      return AuthResult(
        token: token,
        username: username,
      );
    }

    return null;
  } catch (e) {
    print("LOGIN ERROR: $e"); // ✅ log instead of silent failure
    return null;
  }
}
}