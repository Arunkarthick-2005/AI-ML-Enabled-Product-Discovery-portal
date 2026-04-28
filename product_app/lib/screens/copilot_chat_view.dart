import 'package:flutter/material.dart';
import '../services/copilot_service.dart';

class CopilotChatView extends StatefulWidget {
  /// null → generic copilot
  /// non-null → product-specific copilot
  final String? productId;

  const CopilotChatView({
    super.key,
    this.productId,
  });

  bool get isProductCopilot => productId != null;

  @override
  State<CopilotChatView> createState() => _CopilotChatViewState();
}

class _CopilotChatViewState extends State<CopilotChatView> {
  final TextEditingController _controller = TextEditingController();
  final List<_ChatMessage> _messages = [];
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();

    // Only add greeting for PRODUCT copilot
    if (widget.isProductCopilot) {
      _messages.add(
        _ChatMessage(
          text: "👋 Ask me anything about this product.",
          isUser: false,
        ),
      );
    }
  }

  Future<void> _sendMessage() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _isLoading) return;

    setState(() {
      _messages.add(_ChatMessage(text: text, isUser: true));
      _controller.clear();
      _isLoading = true;
    });

    try {
      final answer = widget.isProductCopilot
          ? await CopilotService.askCopilotForProduct(
              question: text,
              productId: widget.productId!,
            )
          : await CopilotService.askCopilot(text);

      setState(() {
        _messages.add(
          _ChatMessage(text: answer, isUser: false),
        );
      });
    } finally {
      setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,

      // ✅ ONLY show AppBar for PRODUCT copilot
      appBar: widget.isProductCopilot
          ? AppBar(
              backgroundColor: Colors.blue,
              title: const Text(
                "Product Copilot",
                style: TextStyle(fontWeight: FontWeight.w600),
              ),
            )
          : null,

      body: Column(
        children: [
          // ✅ GENERIC COPILOT EMPTY STATE
          if (!widget.isProductCopilot && _messages.isEmpty)
            _buildGenericIntro(),

          // CHAT MESSAGES
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.all(12),
              itemCount: _messages.length,
              itemBuilder: (_, i) =>
                  _ChatBubble(message: _messages[i]),
            ),
          ),

          if (_isLoading)
            const Padding(
              padding: EdgeInsets.all(8),
              child: CircularProgressIndicator(),
            ),

          // INPUT BAR
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.white,
              border: Border(
                top: BorderSide(color: Colors.grey.shade300),
              ),
            ),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _controller,
                    onSubmitted: (_) => _sendMessage(),
                    decoration: const InputDecoration(
                      hintText: "Ask Copilot…",
                      border: OutlineInputBorder(),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton(
                  icon: const Icon(Icons.send, color: Colors.blue),
                  onPressed: _sendMessage,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ✅ GENERIC COPILOT INTRO UI
  Widget _buildGenericIntro() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Card(
        elevation: 0,
        color: Colors.grey.shade100,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: const [
              Text(
                "👋 Hi! I'm your Copilot...\n"
                "You can ask anything about the product which are available...\n",
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ChatMessage {
  final String text;
  final bool isUser;

  _ChatMessage({
    required this.text,
    required this.isUser,
  });
}

class _ChatBubble extends StatelessWidget {
  final _ChatMessage message;

  const _ChatBubble({required this.message});

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: message.isUser
          ? Alignment.centerRight
          : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: message.isUser
              ? Colors.blue.shade100
              : Colors.grey.shade200,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Text(
          message.text,
          style: const TextStyle(fontSize: 14),
        ),
      ),
    );
  }
}