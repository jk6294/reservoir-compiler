function [A, B, rs, xs, dt, gam, d, W] = runMethod(A, B, rs, xs, dt, gam, sym_eqs, verbose)
%% Initialize reservoir
rng(0);  
m = size(xs, 1);
RO = ReservoirTanhB(A,B,rs,xs,dt,gam);
d = RO.d;

%% Decompile RNN into dNPL
dv = A*rs + B*xs + d;
[Pd1,C1] = decomp_poly1_ns(A, B, rs, dv, 4);

% Compute shift matrix
[Pdx,Pdy] = find((sum(Pd1,2)+sum(Pd1,2)') <= max(sum(Pd1,2)));
PdS = zeros(size(Pd1,1));
for i = 1:length(Pdx)
    PdS(Pdx(i),Pdy(i)) = find(sum(Pd1==(Pd1(Pdx(i),:)+Pd1(Pdy(i),:)),2)==m);
end

%% Convert Symbolic Equations -- NEW
syms t; assume(t,'real'); 
syms x(t) [m,1]; x = x(t); assume(x,'real');

[output_eqs, recurrences, my_x] = eqs_py2mat(sym_eqs);
%% Shift && Compile
input_vector = sym(zeros(m, 1));
% generate input vector by checking for recurrences
for i = 1:length(recurrences)
    % get input & output #
    recurrence = recurrences{i};
    tokens = regexp(recurrence, 'o(\d+) == x(\d+)', 'tokens');
    if ~isempty(tokens)
        outputIndex = str2double(tokens{1}{1}); % o1 -> 1
        inputIndex = str2double(tokens{1}{2});  % x3 -> 3
    end

    % set recurrences to input vector
    input_vector(inputIndex) = 10 * output_eqs{outputIndex}; %TODO: why multiply by 10??
end

% Shift basis
pr = primes(2000)'; pr = pr(1:m);
[~,DX] = sym2deriv(input_vector,my_x,pr,Pd1,PdS);

% Finish generating basis
Aa  = zeros(size(C1));
Aa(:,(1:m)+1)  = Aa(:,(1:m)+1)+B;
Aa(:,1) = Aa(:,1) + d;
RdNPL = gen_basis(Aa,PdS);

% Compile
o = zeros(length(output_eqs),size(C1,2)); % Create the o matrix as zeros
oS = [];

% Put 1s at recurrent inputs in o
for i = 1:length(recurrences)
    % get input & output #
    recurrence = recurrences{i};
    tokens = regexp(recurrence, 'o(\d+) == x(\d+)', 'tokens');
    if ~isempty(tokens)
        outputIndex = str2double(tokens{1}{1}); % o1 -> 1
        inputIndex = str2double(tokens{1}{2});  % x3 -> 3
    end
    o(outputIndex, inputIndex + 1) = 1;
    oS = [oS; DX(inputIndex, :)];
end

%TODO: - if no recurrence, oS is not being set!

%oS = DX(end,:); % indexing is a problem here! oS writes the terms from the symbolic equations in terms symbolic bases from Pd1
%oS = DX(1,:); % should be taking from all reccurent inputs.

OdNPL = o+oS/gam; % combines o and oS. Why divide by gam??
% Hacky Partial Sol'n for Lorenz
% OdNPL(2, 2) = 1;
% OdNPL(1, 3) = -1;
% OdNPL(3, 4) = 1;
W = lsqminnorm(RdNPL', OdNPL')';

% Test for compilation accuracy
if verbose
    disp(['Compiler residual: ' num2str(norm(W*RdNPL - OdNPL))]);
end
%% Internalize recurrences -- NEW
reccA = A;
extB = B;
new_x = zeros(m, 1);
for i = 1:length(recurrences)
    % get input & output #
    recurrence = recurrences{i};
    tokens = regexp(recurrence, 'o(\d+) == x(\d+)', 'tokens');
    if ~isempty(tokens)
        outputIndex = str2double(tokens{1}{1}); % o1 -> 1
        inputIndex = str2double(tokens{1}{2});  % x3 -> 3
    end

    % internalize to adjacency/ splice B
    reccA = reccA + B(:, inputIndex)* W(outputIndex, :);

    if size(new_x, 1) == 1
        extB = zeros(size(extB, 1), 1);
        new_x = 0;
    else
        extB(:, inputIndex) = [];
        new_x(inputIndex) = [];
    end
    
end

RP = ReservoirTanhB(reccA,extB,rs, new_x,dt,gam);
RP.d = d;
A = reccA;
B = extB;
xs = new_x;

