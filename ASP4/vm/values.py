"""VBScript runtime values and sentinels."""


class _Sentinel:
    def __init__(self, name: str):
        self.name = name
    def __repr__(self):
        return self.name
    def __call__(self, *args, **kwargs):
        # Allow sentinel to be called and return self or empty?
        # This prevents "Not callable: CBOOL (_Sentinel)" if CBOOL resolves to VBEmpty (which is _Sentinel).
        # VBScript functions often return Empty on error, and if that Empty is stored in a variable and called...
        # Wait, if CBOOL is a function, and it resolved to VBEmpty, that means the function definition is missing.
        # But if we want to suppress the error and return Empty (like a permissive shim), we can.
        # However, correct VBScript behavior is Type Mismatch if calling a non-function.
        # The user reported "Not callable: CBOOL (_Sentinel)". This confirms CBOOL resolved to a Sentinel.
        # Since we fixed the injection, CBOOL should resolve to a function.
        # But for robust runtime, let's make Sentinel raise VBScriptRuntimeError("Type mismatch")
        # instead of being uncallable (which raises TypeError in python interpreter logic).
        # Actually interpreter checks callable(). _Sentinel with __call__ is callable.
        # If we make it callable, we can raise the correct VBScript error inside.
        #import traceback
        #print(f"DEBUG: Calling Sentinel {self.name} with args={args}")
        #traceback.print_stack()
        from ..vb_errors import raise_runtime
        raise_runtime('TYPE_MISMATCH', f"Expected function, got {self.name}")

VBEmpty = _Sentinel("VBEmpty")
VBNull = _Sentinel("VBNull")
VBNothing = _Sentinel("VBNothing")


class VBArray:
    """VBScript-like array (supports 1-D and multi-D).

    - Lower bounds are always 0.
    - Storage order matches VB/VBScript: column-major (first dimension varies fastest).
    - Dynamic arrays exist with allocated=False until ReDim.
    """

    def __init__(self, upper_bounds, allocated: bool = True, dynamic: bool = False):
        if isinstance(upper_bounds, int):
            upper_bounds = [upper_bounds]
        self._ubs = [int(x) for x in upper_bounds]
        self._dims = len(self._ubs)
        self._allocated = bool(allocated)
        self._dynamic = bool(dynamic)
        self._items = []
        if self._allocated:
            self._alloc_items(fill="")

    def _size(self):
        if not self._allocated:
            return 0
        size = 1
        for ub in self._ubs:
            size *= (ub + 1)
        return size

    def _alloc_items(self, fill=VBEmpty):
        # treat negative ub as empty
        for ub in self._ubs:
            if ub < 0:
                self._items = []
                return
        self._items = [fill for _ in range(self._size())]

    def dims(self):
        return self._dims

    def lbound(self, dim: int = 1):
        return 0

    def ubound(self, dim: int = 1):
        if not self._allocated:
            raise IndexError("Subscript out of range")
        d = int(dim)
        if d < 1 or d > self._dims:
            raise IndexError("Subscript out of range")
        return self._ubs[d - 1]

    def _flat_index(self, indices):
        if not self._allocated:
            raise IndexError("Subscript out of range")
        if isinstance(indices, (int, str)):
            indices = [indices]
        if len(indices) != self._dims:
            raise IndexError("Subscript out of range")
        idxs = [int(x) for x in indices]
        # bounds check
        for d, i in enumerate(idxs):
            if i < 0 or i > self._ubs[d]:
                raise IndexError("Subscript out of range")
        # VB/VBScript column-major: first dimension varies fastest.
        flat = 0
        stride = 1
        for d in range(0, self._dims):
            flat += idxs[d] * stride
            stride *= (self._ubs[d] + 1)
        return flat

    def __vbs_index_get__(self, index):
        flat = self._flat_index(index)
        return self._items[flat]

    def __vbs_index_set__(self, index, value):
        flat = self._flat_index(index)
        self._items[flat] = value

    def __iter__(self):
        if not self._allocated:
            return iter([])
        return iter(self._items)

    def redim(self, upper_bounds, preserve: bool = False):
        if isinstance(upper_bounds, int):
            upper_bounds = [upper_bounds]
        new_ubs = [int(x) for x in upper_bounds]
        if not preserve:
            self._ubs = new_ubs
            self._dims = len(new_ubs)
            self._allocated = True
            self._alloc_items(fill=VBEmpty)
            return

        # Preserve rules: same dims, all but last dimension must match.
        if not self._allocated:
            # Preserve on unallocated behaves like normal ReDim
            self._ubs = new_ubs
            self._dims = len(new_ubs)
            self._allocated = True
            self._alloc_items(fill=VBEmpty)
            return
        if len(new_ubs) != self._dims:
            # Different number of dimensions with Preserve: use temp array workaround
            self._redim_preserve_workaround(new_ubs)
            return
        if self._dims > 1:
            for d in range(self._dims - 1):
                if new_ubs[d] != self._ubs[d]:
                    # Non-last dimension changed with Preserve: use temp array workaround
                    self._redim_preserve_workaround(new_ubs)
                    return

        old_items = self._items
        old_ubs = list(self._ubs)

        self._ubs = new_ubs
        self._allocated = True
        self._alloc_items(fill=VBEmpty)

        # Copy overlap region with correct storage order.
        overlap = [min(old_ubs[d], new_ubs[d]) for d in range(self._dims)]

        def rec(dim, idxs):
            if dim == self._dims:
                # compute flat indexes in old/new via column-major
                of = 0
                nf = 0
                stride_o = 1
                stride_n = 1
                for d in range(self._dims):
                    of += idxs[d] * stride_o
                    nf += idxs[d] * stride_n
                    stride_o *= (old_ubs[d] + 1)
                    stride_n *= (new_ubs[d] + 1)
                self._items[nf] = old_items[of]
                return
            for i in range(overlap[dim] + 1):
                idxs.append(i)
                rec(dim + 1, idxs)
                idxs.pop()

        rec(0, [])

    def clone(self):
        if not self._allocated:
            return VBArray(self._ubs, allocated=False, dynamic=self._dynamic)
        c = VBArray(self._ubs, allocated=True, dynamic=self._dynamic)
        c._items = list(self._items)
        return c

    def _redim_preserve_workaround(self, new_ubs):
        """Workaround for VBScript limitation: ReDim Preserve on multiple dimensions.
        
        Creates a new array with the new dimensions and copies all existing data.
        This emulates the behavior that VBScript+IIS would allow if it supported
        changing all dimensions with Preserve.
        """
        old_items = list(self._items)
        old_ubs = list(self._ubs)
        old_dims = self._dims
        
        # Create new array with new dimensions
        self._ubs = new_ubs
        self._dims = len(new_ubs)
        self._allocated = True
        self._alloc_items(fill=VBEmpty)
        
        # Calculate minimum dimensions to copy
        copy_dims = min(old_dims, self._dims)
        overlap = []
        for d in range(copy_dims):
            overlap.append(min(old_ubs[d], new_ubs[d]))
        
        # Add extra dimensions (use 0 if old had fewer)
        for d in range(copy_dims, self._dims):
            overlap.append(new_ubs[d])
        
        # Copy data using recursive traversal
        def rec(dim, idxs):
            if dim == self._dims:
                # Compute flat indexes for both old and new arrays
                # Handle case where dimensions differ
                old_idxs = []
                for d in range(old_dims):
                    if d < len(idxs):
                        old_idxs.append(idxs[d])
                    else:
                        old_idxs.append(0)
                
                of = 0
                nf = 0
                stride_o = 1
                stride_n = 1
                for d in range(old_dims):
                    of += old_idxs[d] * stride_o
                    stride_o *= (old_ubs[d] + 1)
                for d in range(self._dims):
                    nf += idxs[d] * stride_n
                    stride_n *= (new_ubs[d] + 1)
                
                if of < len(old_items):
                    self._items[nf] = old_items[of]
                return
            for i in range(overlap[dim] + 1):
                idxs.append(i)
                rec(dim + 1, idxs)
                idxs.pop()
        
        rec(0, [])

    def erase(self):
        # VBScript: Erase on dynamic arrays deallocates.
        if self._dynamic:
            self._allocated = False
            self._items = []
            self._ubs = [-1 for _ in range(self._dims)]
            return
        if not self._allocated:
            return
        for i in range(len(self._items)):
            self._items[i] = ""

    def __repr__(self):
        if not self._allocated:
            return f"VBArray(unallocated dims={self._dims})"
        return f"VBArray(ubs={self._ubs})"
