"""
Author: Jacob Hess
Date: July 2021

Description: This code solves the social planner's problem for deterministic neoclassical growth model. Since the 
welfare theorems hold the solution coincides with the competitive equilibrium solution. The model is solved using 
value function interation. The code also computes a perfect foresight transition to the steady state where it 
interpolates the next period capital policy function by either cubic interpolation or approximating it with 
chebyshev polynomials and OLS.

Acknowledgements:
    1) Heer and Maussner Ch. 4
    2) Fabrice Collard's "Value Iteration" notes (http://fabcol.free.fr/notes.html)
    
Required packages: 
    -- Packages from the anaconda distribution. (to install for free: https://www.anaconda.com/products/individual
                                                 
Requirements file:
    -- Accompanying requirements.txt contains the versions of the library and packages versions that I used.
    -- Not required to use, but I recommend doing so if you either have trouble running this file or figures generated do not coincide with mine. 
    -- In your termain run the following 
        * pip install -r /your path/requirements.txt                                            
"""

import time
import numpy as np
from scipy import interpolate
from numba import njit, prange
import matplotlib.pyplot as plt
import seaborn as sns
sns.set(style='whitegrid')

#############
# I. Model  #
############


class ncgmVFI:
    
    ############
    # 1. setup #
    ############

    def __init__(self, plott =1, transition=1, interpolate_type = 'chebyshev'):              
            
            #parameters subject to changes
            self.plott = plott      #select 1 to make plots
            self.transition = transition        # select 1 to do transition
            self.interpolate_type = interpolate_type    #interpolation for transition. options: 'cubic', 'chebyshev'. if transition=0 then this option is automatically ignored.
            
            self.setup_parameters()
            self.setup_grid()
        
            self.params = self.sigma, self.beta, self.delta, self.alpha, self.grid_k, self.Nk, self.maxit, self.tol
            
            # warnings
             
            if self.plott != 1 and self.plott != 0:
                raise Exception("Plot option incorrectly entered: Choose either 1 or 0.")
            
            if self.transition != 1 and self.transition != 0:
                raise Exception("Transition option incorrectly entered: Choose either 1 or 0.")
                
            if self.interpolate_type != 'chebyshev' and self.interpolate_type != 'cubic':
                raise Exception("Interpolation for transition option incorrectly entered: Choose either 'chebyshev' or 'cubic'")
                
                

    def setup_parameters(self):

        # a. model parameters
        self.sigma=2    #crra coefficient
        self.beta = 0.95  # discount factor
        self.rho = (1-self.beta)/self.beta #discount rate
        self.delta = 0.1  # depreciation rate
        self.alpha = 1/3  # cobb-douglas coeffient
        
        # b. steady state solution
        self.k_ss = (self.alpha/(1/self.beta - (1-self.delta)))**(1/(1 - self.alpha)) #capital
        self.c_ss = self.k_ss**(self.alpha) - self.delta*self.k_ss #consumption
        self.i_ss = self.delta*self.k_ss    #investment
        self.y_ss = self.k_ss**(self.alpha) #output

        # c. vfi solution
        self.tol = 1e-6  # tolerance for vfi
        self.maxit = 2000  # maximum number of iterations 

        # capital grid 
        self.Nk = 1000
        self.dev = 0.9
        self.k_min = (1-self.dev)*self.k_ss
        self.k_max = (1+self.dev)*self.k_ss
        
        # d. transition
        self.sim_T = 75    #number of transition periods
        self.perc = 0.5     #percentage below the steady state where transition starts
        self.cheb_order = 10    #chebyshev polynomial order
        
    def setup_grid(self):
        # a. capital grid
        self.grid_k = np.linspace(self.k_min, self.k_max, self.Nk)
        
    
    
    
    ########################
    # 2. Helper Functions #
    #######################
    
    
    
    def grid_to_nodes(self, x, x_min, x_max):
        """
        Scales x \in [x_min,x_max] to z \in [-1,1]
        """    
        
        return (2 * (x - x_min) / (x_max - x_min)) - 1
        
    def chebyshev_polynomial(self, roots, n):
        """ 
        Constructs a psuedo-Vandermonde matrix of Chebyshev polynomial expansion using the recurrence relation
        
        This function is equivalent to np.polynomial.chebyshev.chebvander(roots, n-1)
        """
        T = np.zeros((np.size(roots),n))
    
        T[:,0] = np.ones((np.size(roots),1)).T
    
        T[:,1] = roots.T
    
        for i in range(1,n-1):
            T[:,i+1] = 2 * roots * T[:,i] - T[:,i-1]
            
        return T



    ##################
    # 3. Transition #
    #################
    
    
    
    def perfect_foresight_transition(self):
        """
        Calculates the transition of the economy to the steady state. The interpolation of the 
        capital policy function is done by either cubic interpolation or approximating the policy
        function with chebyshev polynomials and OLS.
        
        Returns the transition path of capital, consumption, output and investment.
        """
        
        # a. initialize
        trans_k = np.zeros(self.sim_T+1)
        trans_k[0] = self.perc*self.k_ss    #starting point
        
        
        
        # b. transition with cubic interpolation
        if self.interpolate_type == 'cubic': 
            
            # i. interpolant function
            k_interpolant = interpolate.interp1d(self.grid_k, self.pol_kp, kind='cubic')
            
            # ii. iterate forward and interpolate
            for it in range(self.sim_T):
                trans_k[it+1] = k_interpolant(trans_k[it])
                
                
                
        # c. chebyshev approximation of capital policy function
        
        if self.interpolate_type == 'chebyshev':
            
            # i. convert capital grid to chebyshev root
            roots_k = self.grid_to_nodes(self.grid_k, self.k_min, self.k_max)
            
            # ii. matrix of chebyshev polynomials
            Tk = self.chebyshev_polynomial(roots_k, self.cheb_order)
            
            # iii. compute OLS
            theta = np.linalg.lstsq(Tk, self.pol_kp, rcond=None)[0]
            
            # view approximation 
            
            if self.plott:
                plt.plot(self.grid_k, self.pol_kp)
                plt.plot(self.grid_k, np.dot(Tk,theta), linestyle='--')
                plt.title('Chebyshev Approximation of Capital Policy Function')
                plt.legend(['True Policy Function', 'Chebyshev Approximated Policy Function'])
                plt.xlabel('Capital Grid')
                #plt.savefig('Figures Transition/cheby_approx_ncgm_vfi.pdf')
                plt.show()
                
            # iv. iterate forward
            for it in range(self.sim_T):
                # convert capital value to chebyshev node
                root_kt = self.grid_to_nodes(trans_k[it], self.k_min, self.k_max)
                
                # matrix of chebyshev polynomials for given node
                Tkt = self.chebyshev_polynomial(root_kt, self.cheb_order)
                
                # interpolate 
                trans_k[it+1] = np.dot(Tkt, theta)
                
                
        # d. get the other variables
        
        trans_output = trans_k[0:-1]**self.alpha
        
        trans_inv = trans_k[1:] - (1-self.delta)*trans_k[0:-1]
        
        trans_cons = trans_output - trans_inv
            
        return trans_k, trans_cons, trans_output, trans_inv
            
        


    ######################
    # 4. Main Function  #
    #####################
    
    def solve_model(self):
        """
        Runs the entire model.
        """  
        
        t0 = time.time()    #start the clock
        
        
        # a. solve social planer's problem
        
        print("\nSolving social planner problem...")
    
        self.VF, self.pol_kp, self.pol_cons, self.it = vfi_det(self.params)
        
        if self.it < self.maxit-1:
            print(f"Convergence in {self.it} iterations.")
        else : 
            print("No convergence.")
            
        t1 = time.time()
        print(f'Value function iteration time elapsed: {t1-t0:.2f} seconds')
        
        
        
        
        # b. steady state transition
        
        if self.transition:
            
            print("\nSteady State Transition...")
            
            self.trans_k, self.trans_cons, self.trans_output, self.trans_inv = self.perfect_foresight_transition()
        
            t2 = time.time()
            print(f'Transition iteration time elapsed: {t2-t1:.2f} seconds')
        
        else : 
            t2 = time.time()
            
        
        
        
        # c. plot
        
        if self.plott:
            
            print('\nPlotting...')
            
            # i. solutions
            plt.plot(self.grid_k, self.VF)
            plt.title('Value Function')
            plt.xlabel('Capital Stock')
            #plt.savefig('Figures Solution/vf_ncgm_vfi.pdf')
            plt.show()
            
            plt.plot(self.grid_k, self.pol_kp)
            plt.title('Next Period Capital Stock Policy Function')
            plt.xlabel('Capital Stock')
            plt.plot([self.k_min,self.k_max], [self.k_min,self.k_max],linestyle=':')
            plt.legend(['Policy Function', '45 Degree Line'])
            #plt.savefig('Figures Solution/capital_policyfun_ncgm_vfi.pdf')
            plt.show()
    
            plt.plot(self.grid_k, self.pol_cons)
            plt.title('Consumption Policy Function')
            plt.xlabel('Capital Stock')
            #plt.savefig('Figures Solution/consumption_policyfun_ncgm_vfi.pdf')
            plt.show()
            
            # ii. transition figures
            if self.transition:
                plt.plot(np.arange(self.sim_T), self.trans_k[:-1])
                plt.plot(np.arange(self.sim_T), self.k_ss*np.ones(self.sim_T), linestyle='--')
                plt.title('Transition Dynamics: Capital Stock')
                plt.xlabel('Time')
                #plt.savefig('Figures Transition/capital_transition_ncgm_vfi.pdf')
                plt.show()
                
                plt.plot(np.arange(self.sim_T), self.trans_cons)
                plt.plot(np.arange(self.sim_T), self.c_ss*np.ones(self.sim_T), linestyle='--')
                plt.title('Transition Dynamics: Consumption')
                plt.xlabel('Time')
                #plt.savefig('Figures Transition/consumption_transition_ncgm_vfi.pdf')
                plt.show()
                
                plt.plot(np.arange(self.sim_T), self.trans_output)
                plt.plot(np.arange(self.sim_T), self.y_ss*np.ones(self.sim_T), linestyle='--')
                plt.title('Transition Dynamics: Output')
                plt.xlabel('Time')
                #plt.savefig('Figures Transition/output_transition_ncgm_vfi.pdf')
                plt.show()
                
                plt.plot(np.arange(self.sim_T), self.trans_inv)
                plt.plot(np.arange(self.sim_T), self.i_ss*np.ones(self.sim_T), linestyle='--')
                plt.title('Transition Dynamics: Investment')
                plt.xlabel('Time')
                #plt.savefig('Figures Transition/investment_transition_ncgm_vfi.pdf')
                plt.show()
            
            
            t3 = time.time()
            print(f'Plot time elapsed: {t3-t2:.2f} seconds')
            
        t4 = time.time()
        print(f'\nTotal Run Time: {t4-t0:.2f} seconds')
  




#########################
# II. Jitted Functions  #
########################

#########################
# 1. Helper Functions  #
########################
        

@njit    
def utility(c, sigma):
    eps = 1e-8
    
    if  sigma == 1:
        return np.log(np.fmax(c, eps))
    else:
        return (np.fmax(c, eps) ** (1 - sigma) -1) / (1 - sigma)
    
    
    
    
#################################
# 2. Value Function Iteration  #
################################

@njit(parallel=True)
def vfi_det(params):
   
    """
    Value function iteration to solve the social planner problem
    
    *Input
        *Model parameters
    
    *Output
        * VF is value function
        * pol_kp is k' or savings policy function
        * pol_cons is the consumption policy function
        * it is the iteration number 
    """

    # a. Initialize counters, initial guess. storage matriecs
    
    sigma, beta, delta, alpha, grid_k, Nk, maxit, tol = params
    
    VF_old    = np.zeros(Nk)  #initial guess
    VF = np.copy(VF_old)    #contracted value function aka Tv
    pol_kp = np.copy(VF_old)    
    pol_cons = np.copy(VF_old)
    
    # b. Iterate
    for it in range(maxit) :
        for ik in prange(Nk):
            
            # i. resource constrant
            c = grid_k[ik]**alpha + (1-delta)*grid_k[ik] - grid_k
            
            # ii. utility and impose nonnegativity for consumption
            util = utility(c, sigma)
            util[c < 0] = -10e10
            
            # iii. value and policy functions
            RHS = util + beta*VF_old   #RHS of Bellman
            
            VF[ik] = np.max(RHS) #take maximum value for value function
            
            pol_kp[ik] = grid_k[np.argmax(RHS)]    #policy function for how much to save
       
        # iv. calculate su-norm
        dist = np.abs(VF-VF_old).max()
       
        if dist < tol :
            break
        
        VF_old = np.copy(VF)
        
    # v. consumption policy function
    pol_cons = grid_k**alpha + (1-delta)*grid_k - pol_kp
 
    
    return VF, pol_kp, pol_cons, it
        


# run everything
ncgm_det = ncgmVFI()
ncgm_det.solve_model()

