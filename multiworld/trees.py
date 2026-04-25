struct SplayNode{
	SplayNode(){}
	SplayNode(T value_arg): value{value_arg} {}
	T value{}; //!< Value associated with node
	array<SplayNode *, 2> child{}; //!< Left and right children
	SplayNode *parent{}; //!< Pointer to parent
	Node* path_parent{}; // Added for link-cut tree
	bool side() const {
		/*! Returns true if child is on the right, and false otherwise*/
		return parent->child[1] == &this;
	}
	void rotate() {
		/*! Rotate node x around its parent */
		const auto p = parent;
		const bool i = side();

		if (p->parent) {
			p->parent->attach(p->side(), &this);
		} else {
			parent = nullptr;
		}
		p->attach(i, child[!i]);
		attach(!i, p);
		this.path_parent = p->path_parent; // Added for link-cut tree
	}
	void splay() {
		/*! Splay node x. x will become the root of the tree*/
		for(;parent;rotate()) {
			if (parent->parent) {
			  (side() == parent->side() ? parent: &this)->rotate();
			}
		}
	}
	array<SplayNode *, 2> split() {
		splay();
		// TODO use detach function
		const auto right = child[1];
		if (right) {
			right->parent = nullptr;
		}
		this->right = nullptr;
		return {&this, right};
	}
	void attach(bool side, SplayNode *const new_) {
		/*! Attach node new_ as the node's side children*/
		if (new_) {
			new_->parent = &this;
		}
		child[side] = new_;
	}
};

Node *make_tree() {
	/*! Make a new tree */
	return new Node{};
}
void detach_child(Node* node){
	/*! Converts node's preferred child edge to a path parent edge*/
	if(node->child[1]){
		node->child[1]->path_parent = node;
		node->child[1]->parent = nullptr;
	}
}
Node *access(Node *node) {
	/*! Moves node to the root of the auxillary tree containing the root node of the tree. Returns last path-parent of node as it moves up the tree*/
	node->splay();
	detach_child(node);
	node->child[1] = nullptr;
	Node *par = node;
	while (node->path_parent) {
		par = node->path_parent;
		par->splay();
		detach_child(par);
		par->attach(1, node);
		node->path_parent = nullptr;
		node->splay();
	}
	return par;
}
