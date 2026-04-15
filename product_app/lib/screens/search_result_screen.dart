import 'package:flutter/material.dart';
import '../models/product.dart';
import '../services/product_service.dart';
import 'product_detail_screen.dart';

class SearchResultScreen extends StatelessWidget {
  final String query;

  const SearchResultScreen({super.key, required this.query});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Results for "$query"')),
      body: FutureBuilder<List<Product>>(
        future: ProductService.searchProducts(query: query),
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }

          if (snapshot.hasError) {
            return Center(child: Text(snapshot.error.toString()));
          }

          final products = snapshot.data!;

          if (products.isEmpty) {
            return const Center(child: Text("No products found"));
          }

          return ListView.builder(
            itemCount: products.length,
            itemBuilder: (context, index) {
              final product = products[index];

              return ListTile(
                leading: product.images.isNotEmpty
                    ? Image.network(
                        "http://localhost:8000/image-proxy?url=${Uri.encodeComponent(product.images[0])}",
                        width: 50,
                        height: 50,
                        fit: BoxFit.cover,
                      )
                    : const Icon(Icons.image),

                title: Text(product.title),
                subtitle: Text(product.brand ?? ""),

                onTap: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => ProductDetailScreen(
                        productId: product.pid,
                      ),
                    ),
                  );
                },
              );
            },
          );
        },
      ),
    );
  }
}