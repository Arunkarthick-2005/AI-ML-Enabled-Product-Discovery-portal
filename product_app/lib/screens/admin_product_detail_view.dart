import 'package:flutter/material.dart';
import '../models/product.dart';
import '../services/product_service.dart';

class AdminProductDetailView extends StatefulWidget {
  final String productId;

  const AdminProductDetailView({
    super.key,
    required this.productId,
  });

  @override
  State<AdminProductDetailView> createState() =>
      _AdminProductDetailViewState();
}

class _AdminProductDetailViewState
    extends State<AdminProductDetailView> {

  late Future<Product> _productFuture;

  @override
  void initState() {
    super.initState();
    _productFuture =
        ProductService.fetchProductById(widget.productId);
  }

  String _price(Product p) =>
      p.price is Map && p.price['selling'] != null
          ? "₹${p.price['selling']}"
          : "N/A";

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Product>(
      future: _productFuture,
      builder: (context, snapshot) {
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }

        final product = snapshot.data!;

        return SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [

              // ✅ IMAGE (DIRECT URL ✅)
              SizedBox(
                height: 220,
                width: double.infinity,
                child: product.images.isNotEmpty
                    ? PageView(
                  children: product.images.map((img) {

                    final proxyUrl =
                        "http://10.0.2.2:8000/image-proxy?url=${Uri.encodeComponent(img)}";

                    return Image.network(
                      proxyUrl, // ✅ PROXY ADDED
                      fit: BoxFit.contain,
                      errorBuilder: (_, __, ___) =>
                      const Icon(Icons.broken_image),
                    );

                  }).toList(),
                )
                    : Container(
                  color: Colors.grey.shade200,
                  child: const Icon(Icons.image),
                ),
              ),

              const SizedBox(height: 16),

              // ✅ TITLE
              Text(
                product.title,
                style: const TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold),
              ),

              const SizedBox(height: 4),

              // ✅ BRAND
              Text(
                product.brand ?? "",
                style: TextStyle(color: Colors.grey.shade600),
              ),

              const SizedBox(height: 8),

              // ✅ PRICE
              Text(
                _price(product),
                style: const TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.bold),
              ),

              const Divider(height: 32),

              // ✅ DESCRIPTION
              const Text("Description",
                  style: TextStyle(fontWeight: FontWeight.bold)),

              const SizedBox(height: 6),

              Text(
                product.description.isNotEmpty
                    ? product.description
                    : "No description available",
              ),

              const Divider(height: 32),

              // ✅ SPECIFICATIONS
              const Text("Specifications",
                  style: TextStyle(fontWeight: FontWeight.bold)),

              const SizedBox(height: 8),

              _specs(product.specifications),

              const SizedBox(height: 20),
            ],
          ),
        );
      },
    );
  }

  // ✅ SPECIFICATION DISPLAY
  Widget _specs(dynamic specs) {
    if (specs == null ||
        specs is! Map ||
        !specs.containsKey('product_specification')) {
      return const Text("No specifications");
    }

    final List list = specs['product_specification'];

    return Column(
      children: list.map((s) {
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Row(
            children: [
              Expanded(
                flex: 4,
                child: Text(
                  s['key'],
                  style: const TextStyle(
                      fontWeight: FontWeight.w600),
                ),
              ),
              Expanded(
                flex: 6,
                child: Text(s['value']),
              ),
            ],
          ),
        );
      }).toList(),
    );
  }
}
